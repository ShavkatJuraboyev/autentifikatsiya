import os
import base64
import io
import json
import cv2
import numpy as np
from PIL import Image
from deepface import DeepFace
import jwt
import logging
from datetime import datetime, timedelta
from django.contrib import messages
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseRedirect
from django.views import View
from django.utils.crypto import get_random_string
from django.conf import settings

from users.models import CustomUser, IntegrationApplication, AccessToken

logger = logging.getLogger(__name__)
User = get_user_model()

def verify_face(input_path, user_face_path, threshold=0.5):
    try:
        result = DeepFace.verify(
            img1_path=input_path,
            img2_path=user_face_path,
            model_name="ArcFace",
            detector_backend="opencv",
            distance_metric="cosine"
        )
        return result.get("distance") < threshold
    except Exception:
        return False

def is_fully_visible_face(pil_image):
    import mediapipe as mp
    mp_face_mesh = mp.solutions.face_mesh
    image = np.array(pil_image)

    with mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.5) as face_mesh:
        results = face_mesh.process(image)
        if not results.multi_face_landmarks:
            return False

        face_landmarks = results.multi_face_landmarks[0]
        left_eye = face_landmarks.landmark[33]
        right_eye = face_landmarks.landmark[263]
        nose_tip = face_landmarks.landmark[1]
        mouth = face_landmarks.landmark[13]
        chin = face_landmarks.landmark[152]

        if abs(left_eye.y - right_eye.y) > 0.05 or nose_tip.y >= mouth.y or chin.y <= mouth.y or abs(nose_tip.x - 0.5) > 0.1:
            return False
        return True

def is_looking_up(pil_image):
    cv_img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    for (x, y, w, h) in faces:
        eyes_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        roi_gray = gray[y:y+h, x:x+w]
        eyes = eyes_cascade.detectMultiScale(roi_gray)
        if len(eyes) >= 2:
            return True
    return False

class AuthorizeEndpoint(View):
    def get(self, request):
        client_id = request.GET.get('client_id')
        redirect_uri = request.GET.get('redirect_uri')

        try:
            app = IntegrationApplication.objects.get(client_id=client_id, redirect_uri=redirect_uri, is_approved=True)
        except IntegrationApplication.DoesNotExist:
            return JsonResponse({'error': 'Invalid client_id or redirect_uri'}, status=400)

        if request.user.is_authenticated:
            code = get_random_string(30)
            request.session['auth_code'] = code
            request.session['auth_user_id'] = request.user.id
            request.session['auth_app_id'] = app.id
            return HttpResponseRedirect(f"{redirect_uri}?code={code}")

        return JsonResponse({'error': 'User not authenticated'}, status=401)

class TokenEndpoint(View):
    def post(self, request):
        code = request.POST.get('code')
        client_id = request.POST.get('client_id')
        client_secret = request.POST.get('client_secret')

        try:
            app = IntegrationApplication.objects.get(client_id=client_id, client_secret=client_secret, is_approved=True)
        except IntegrationApplication.DoesNotExist:
            return JsonResponse({'error': 'Invalid client credentials'}, status=400)

        if request.session.get('auth_code') == code and request.session.get('auth_app_id') == app.id:
            try:
                user = User.objects.get(id=request.session.get('auth_user_id'))
            except User.DoesNotExist:
                return JsonResponse({'error': 'User not found'}, status=400)

            access_token = get_random_string(50)
            AccessToken.objects.create(user=user, app=app, token=access_token)
            return JsonResponse({
                'access_token': access_token,
                'token_type': 'Bearer',
                'user_id': user.id
            })
        return JsonResponse({'error': 'Invalid code'}, status=400)

class UserInfoAPI(View):
    def get(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Missing or invalid token'}, status=401)

        token = auth_header.split()[1]
        try:
            access_token = AccessToken.objects.get(token=token)
            if (datetime.now() - access_token.created).total_seconds() > access_token.expires_in:
                return JsonResponse({'error': 'Token expired'}, status=401)
            user = access_token.user
        except AccessToken.DoesNotExist:
            return JsonResponse({'error': 'Invalid token'}, status=401)

        return JsonResponse({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone_number': user.phone_number
        })

@csrf_exempt
def face_register(request):
    if request.method != 'POST':
        return JsonResponse({'message': 'Faqat POST so‘rovi'}, status=405)

    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        phone_number = data.get('phone_number')
        image_data = data.get('image', '').split(',')[1]

        if CustomUser.objects.filter(username=username).exists():
            return JsonResponse({'message': 'Bunday foydalanuvchi mavjud'}, status=400)

        image_bytes = base64.b64decode(image_data)
        pil_image = Image.open(io.BytesIO(image_bytes)).convert('RGB')

        if not is_fully_visible_face(pil_image) or not is_looking_up(pil_image):
            return JsonResponse({'message': 'Iltimos, yuz to‘liq va to‘g‘ri ko‘rinsin!'}, status=400)

        os.makedirs("temp_faces", exist_ok=True)
        input_path = f"temp_faces/{username}_input.jpg"
        pil_image.save(input_path)

        for user in CustomUser.objects.exclude(face_image=None):
            if user.face_image and verify_face(input_path, user.face_image.path):
                os.remove(input_path)
                return JsonResponse({'message': 'Bu yuz allaqachon ro‘yxatdan o‘tgan'}, status=400)

        user = CustomUser.objects.create_user(
            username=username, password=password, email=email, phone_number=phone_number
        )
        user.face_image.save(f"{username}.jpg", io.BytesIO(image_bytes))
        user.save()

        os.remove(input_path)
        return JsonResponse({'message': 'Ro‘yxatdan o‘tish muvaffaqiyatli'})

    except Exception as e:
        logger.error(f"Register error: {e}")
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

        if not is_fully_visible_face(pil_image) or not is_looking_up(pil_image):
            return JsonResponse({'message': 'Yuz to‘liq va to‘g‘ri ko‘rinsin!'}, status=400)

        os.makedirs("temp_faces", exist_ok=True)
        input_path = "temp_faces/temp_login.jpg"
        pil_image.save(input_path)

        for user in CustomUser.objects.exclude(face_image=None):
            if user.face_image and verify_face(input_path, user.face_image.path):
                login(request, user)
                os.remove(input_path)
                return JsonResponse({'message': f"Xush kelibsiz, {user.username}!"})

        os.remove(input_path)
        return JsonResponse({'message': "Foydalanuvchi topilmadi"}, status=404)

    except Exception as e:
        logger.error(f"Login error: {e}")
        return JsonResponse({'message': f'Xatolik: {str(e)}'}, status=500)

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def profile_view(request):
    user = User.objects.get(id=request.user.id)
    if not user:
        return JsonResponse({'error': 'Foydalanuvchi topilmadi'}, status=404)
    return render(request, 'users/profile.html', {'user': user})

@login_required
def submit_application(request):
    if request.method == 'POST':
        print("POST keldi")
        name = request.POST.get('name')
        redirect_uri = request.POST.get('redirect_uri')
        description = request.POST.get('description', '')

        if not name or not redirect_uri:
            messages.error(request, "Iltimos, barcha maydonlarni to‘ldiring.")
            return redirect('submit_application')

        try:
            IntegrationApplication.objects.create(
                user=request.user,
                name=name,
                redirect_uri=redirect_uri,
                description=description
            )
            messages.success(request, "Ariza yuborildi. Admin tasdiqlashini kuting.")
        except Exception as e:
            print("XATOLIK:", e)
            messages.error(request, f"Ariza yuborishda xatolik: {str(e)}")
        return redirect('user_applications')

    return render(request, 'users/submit_app.html')

def index(request):
    return render(request, 'users/login.html')

def register(request):
    return render(request, 'users/register.html')

@login_required
def user_applications(request):
    apps = IntegrationApplication.objects.filter(user=request.user)
    return render(request, 'users/my_applications.html', {'applications': apps})


def face_auth_start(request):
    redirect_url = request.GET.get('redirect_url')
    if not redirect_url:
        return JsonResponse({'error': 'redirect_url kerak'}, status=400)
    request.session['redirect_uri'] = redirect_url
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
