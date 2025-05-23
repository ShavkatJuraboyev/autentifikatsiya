# views.py
import os
import base64
import io
import json
import cv2
import numpy as np
from PIL import Image
from django.http import JsonResponse
from django.contrib.auth import login, logout
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from users.models import CustomUser, IntegrationApplication
from deepface import DeepFace
import jwt
from datetime import datetime, timedelta
import jwt
from django.conf import settings
from users.forms import IntegrationApplicationForm
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
import logging
logger = logging.getLogger(__name__)

User = get_user_model()

def index(request):
    return render(request, 'users/login.html')

def register(request):
    return render(request, 'users/register.html')

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

def is_fully_visible_face(pil_image):
    import mediapipe as mp
    mp_face_mesh = mp.solutions.face_mesh
    image = np.array(pil_image)

    with mp_face_mesh.FaceMesh(static_image_mode=True,
                                max_num_faces=1,
                                refine_landmarks=True,
                                min_detection_confidence=0.5) as face_mesh:

        results = face_mesh.process(image)
        if not results.multi_face_landmarks:
            return False

        face_landmarks = results.multi_face_landmarks[0]
        left_eye = face_landmarks.landmark[33]
        right_eye = face_landmarks.landmark[263]
        nose_tip = face_landmarks.landmark[1]
        mouth = face_landmarks.landmark[13]
        chin = face_landmarks.landmark[152]

        if abs(left_eye.y - right_eye.y) > 0.05:
            return False
        if nose_tip.y >= mouth.y or chin.y <= mouth.y:
            return False
        if abs(nose_tip.x - 0.5) > 0.1:
            return False
        return True

def is_looking_up(pil_image):
    cv_img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) == 0:
        return False

    for (x, y, w, h) in faces:
        eyes_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        roi_gray = gray[y:y+h, x:x+w]
        eyes = eyes_cascade.detectMultiScale(roi_gray)
        if len(eyes) >= 2:
            return True
    return False


@csrf_exempt
def face_register(request):
    if request.method != 'POST':
        return JsonResponse({'message': 'Faqat POST so‘rovi'}, status=405)

    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        email = data.get('email')
        phone_number = data.get('phone_number')
        image_data = data.get('image', '').split(',')[1]

        if CustomUser.objects.filter(username=username).exists():
            return JsonResponse({'message': 'Bunday foydalanuvchi mavjud'}, status=400)

        image_bytes = base64.b64decode(image_data)
        pil_image = Image.open(io.BytesIO(image_bytes)).convert('RGB')

        if not is_fully_visible_face(pil_image):
            return JsonResponse({'message': 'Iltimos, yuz to‘liq ko‘rinsin!'}, status=400)
        if not is_looking_up(pil_image):
            return JsonResponse({'message': 'Kameraga qarang!'}, status=400)

        os.makedirs("temp_faces", exist_ok=True)
        input_path = f"temp_faces/{username}_input.jpg"
        pil_image.save(input_path)

        threshold_value = 0.5

        for user in CustomUser.objects.exclude(face_image=None):
            if not user.face_image: continue
            try:
                result = DeepFace.verify(
                    img1_path=input_path,
                    img2_path=user.face_image.path,
                    model_name="ArcFace",
                    detector_backend="opencv",
                    distance_metric="cosine"
                )
                if result.get("distance") and result["distance"] < threshold_value:
                    os.remove(input_path)
                    return JsonResponse({'message': 'Bu yuz allaqachon ro‘yxatdan o‘tgan'}, status=400)
            except:
                continue

        # ✅ Foydalanuvchini yaratish
        user = CustomUser.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number
        )
        user.face_image.save(f"{username}.jpg", io.BytesIO(image_bytes))
        user.save()

        os.remove(input_path)
        return JsonResponse({'message': 'Ro‘yxatdan o‘tish muvaffaqiyatli'})

    except Exception as e:
        return JsonResponse({'message': f'Xatolik: {str(e)}'}, status=500)



@csrf_exempt
def face_login(request):
    if request.method != 'POST':
        return JsonResponse({'message': "Faqat POST so'rovi"}, status=405)

    try:
        data = json.loads(request.body)
        image_data = data['image'].split(',')[1]
        image_bytes = base64.b64decode(image_data)
        pil_image = Image.open(io.BytesIO(image_bytes)).convert('RGB')

        if not is_fully_visible_face(pil_image):
            return JsonResponse({'message': 'Yuz to‘liq ko‘rinsin!'}, status=400)
        if not is_looking_up(pil_image):
            return JsonResponse({'message': 'Kameraga qarang!'}, status=400)

        os.makedirs("temp_faces", exist_ok=True)
        input_path = "temp_faces/temp_login.jpg"
        pil_image.save(input_path)

        for user in CustomUser.objects.exclude(face_image=None):
            if not user.face_image or not user.face_image.name:
                continue
            try:
                result = DeepFace.verify(
                    img1_path=input_path,
                    img2_path=user.face_image.path,
                    model_name="ArcFace",
                    detector_backend="opencv",
                    distance_metric="cosine"
                )
                distance = result.get("distance")
                logger.info(f"Login: Comparing to {user.username}, Distance: {distance:.4f}")

                if distance is not None and distance < 0.5:
                    login(request, user)
                    os.remove(input_path)
                    return JsonResponse({'message': f"Xush kelibsiz, {user.username}!"})
            except Exception as e:
                logger.warning(f"Login comparison error with {user.username}: {e}")
                continue


        os.remove(input_path)
        return JsonResponse({'message': "Foydalanuvchi topilmadi"}, status=404)

    except Exception as e:
        logger.error(f"Login error: {e}")
        return JsonResponse({'message': f'Xatolik: {str(e)}'}, status=500)

@login_required
def profile_view(request):
    return render(request, 'users/profile.html', {'user': request.user})


def face_auth_start(request):
    redirect_uri = request.GET.get('redirect_uri')
    if not redirect_uri:
        return JsonResponse({'error': 'redirect_uri kerak'}, status=400)
    request.session['redirect_uri'] = redirect_uri
    return render(request, 'users/login.html')  # Kamera orqali yuz login oynasi

@csrf_exempt
def face_login_callback(request):
    if request.method != 'POST':
        return JsonResponse({'message': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        image_data = data.get('image', '').split(',')[1]
        image_bytes = base64.b64decode(image_data)
        pil_image = Image.open(io.BytesIO(image_bytes)).convert('RGB')

        if not is_fully_visible_face(pil_image):
            return JsonResponse({'message': 'Yuz to‘liq ko‘rinsin!'}, status=400)
        if not is_looking_up(pil_image):
            return JsonResponse({'message': 'Kameraga qarang!'}, status=400)

        os.makedirs("temp_faces", exist_ok=True)
        input_path = "temp_faces/temp_login.jpg"
        pil_image.save(input_path)

        for user in User.objects.exclude(face_image=None):
            if not user.face_image or not user.face_image.name: continue
            try:
                result = DeepFace.verify(
                    img1_path=input_path, img2_path=user.face_image.path,
                    model_name="ArcFace", detector_backend="opencv",
                    distance_metric="cosine")
                if result.get("distance") and result["distance"] < 0.5:
                    login(request, user)
                    os.remove(input_path)
                    payload = {
                        'user_id': user.id, 'username': user.username,
                        'exp': datetime.utcnow() + timedelta(minutes=15)
                    }
                    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
                    redirect_uri = request.session.get('redirect_uri')
                    if redirect_uri:
                        return JsonResponse({'redirect_uri': f"{redirect_uri}?token={token}"})
                    return JsonResponse({'message': 'No redirect_uri found'}, status=400)
            except Exception as e:
                logger.warning(f"Comparison error: {e}")
        os.remove(input_path)
        return JsonResponse({'message': 'Foydalanuvchi topilmadi'}, status=404)
    except Exception as e:
        logger.error(f"Login error: {e}")
        return JsonResponse({'message': f'Xatolik: {str(e)}'}, status=500)
    

def callback_view(request):
    token = request.GET.get('token')
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get("user_id")
        username = payload.get("username")

        # Agar user mavjud bo'lsa, sessiyaga yozish
        user, _ = CustomUser.objects.get_or_create(username=username, defaults={"id": user_id})
        login(request, user)
        return redirect('dashboard')  # foydalanuvchi sahifasi
    except jwt.ExpiredSignatureError:
        return render(request, 'error.html', {'message': 'Token eskirgan'})
    except jwt.DecodeError:
        return render(request, 'error.html', {'message': 'Token noto‘g‘ri'})


@login_required
def submit_application(request):
    if request.method == 'POST':
        form = IntegrationApplicationForm(request.POST)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            return JsonResponse({'message': 'Ariza yuborildi. Admin tasdiqlashini kuting.'})
    else:
        form = IntegrationApplicationForm()
    return render(request, 'users/submit_app.html', {'form': form})


@staff_member_required
def application_list(request):
    apps = IntegrationApplication.objects.all()
    return render(request, 'users/applications.html', {'applications': apps})


@login_required
def user_applications(request):
    apps = IntegrationApplication.objects.filter(user=request.user)
    return render(request, 'users/my_applications.html', {'applications': apps})



@staff_member_required
def approve_application(request, app_id):
    app = get_object_or_404(IntegrationApplication, id=app_id)

    if app.is_approved:
        return JsonResponse({'message': 'Allaqachon tasdiqlangan'}, status=400)

    app.approve()

    # ✅ Email yuborish
    send_mail(
        subject='Integratsiya arizangiz tasdiqlandi',
        message=f"""Hurmatli {app.user.username},
    Siz yuborgan "{app.name}" ariza tasdiqlandi.

    Mana sizning ma’lumotlaringiz:
    Client ID: {app.client_id}
    Client Secret: {app.client_secret}

    E’tibor uchun rahmat!
    """,
        from_email=None,
        recipient_list=[app.user.email],
        fail_silently=False,
    )

    return JsonResponse({
        'message': 'Tasdiqlandi va email yuborildi',
        'client_id': app.client_id,
        'client_secret': app.client_secret
    })
