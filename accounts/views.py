import face_recognition
import numpy as np
from django.http import JsonResponse
from django.core.files.base import ContentFile
import base64
from .models import CustomUser
import speech_recognition as sr
from django.core.files.storage import default_storage


def register_face(request):
    if request.method == "POST":
        image_data = request.POST.get("image")  # Foydalanuvchi yuborgan rasm
        user_id = request.POST.get("user_id")

        user = CustomUser.objects.get(id=user_id)

        # Rasmni dekodlash
        image_bytes = base64.b64decode(image_data.split(',')[1])
        image_file = ContentFile(image_bytes, "face.jpg")

        # OpenCV bilan yuzni tanib olish
        np_image = np.frombuffer(image_bytes, dtype=np.uint8)
        face_image = face_recognition.load_image_file(image_file)
        encodings = face_recognition.face_encodings(face_image)

        if encodings:
            user.face_encoding = ",".join(map(str, encodings[0]))  # Encodingni saqlash
            user.save()
            return JsonResponse({"message": "Yuz muvaffaqiyatli ro‘yxatdan o‘tkazildi"})
        else:
            return JsonResponse({"error": "Yuz topilmadi"}, status=400)


def register_voice(request):
    if request.method == "POST" and request.FILES.get("voice"):
        user_id = request.POST.get("user_id")
        voice_file = request.FILES["voice"]

        user = CustomUser.objects.get(id=user_id)
        file_path = default_storage.save(f"voices/{user_id}.wav", voice_file)
        user.voice_sample = file_path
        user.save()

        return JsonResponse({"message": "Ovoz muvaffaqiyatli ro‘yxatdan o‘tkazildi"})
    return JsonResponse({"error": "Ovoz fayli topilmadi"}, status=400)


def login_with_face(request):
    if request.method == "POST":
        image_data = request.POST.get("image")

        image_bytes = base64.b64decode(image_data.split(',')[1])
        image_file = ContentFile(image_bytes, "face.jpg")
        np_image = np.frombuffer(image_bytes, dtype=np.uint8)
        face_image = face_recognition.load_image_file(image_file)
        encodings = face_recognition.face_encodings(face_image)

        if encodings:
            users = CustomUser.objects.exclude(face_encoding=None)
            for user in users:
                stored_encoding = np.array(list(map(float, user.face_encoding.split(","))))
                match = face_recognition.compare_faces([stored_encoding], encodings[0])

                if match[0]:
                    return JsonResponse({"message": f"Xush kelibsiz, {user.username}"})
            return JsonResponse({"error": "Foydalanuvchi topilmadi"}, status=400)
        return JsonResponse({"error": "Yuz topilmadi"}, status=400)


def login_with_voice(request):
    if request.method == "POST" and request.FILES.get("voice"):
        voice_file = request.FILES["voice"]
        recognizer = sr.Recognizer()

        with sr.AudioFile(voice_file) as source:
            audio = recognizer.record(source)

        try:
            transcript = recognizer.recognize_google(audio)  # Ovozdan matn ajratib olish
            users = CustomUser.objects.exclude(voice_sample=None)

            for user in users:
                if user.username.lower() in transcript.lower():  # Matndan foydalanuvchi nomini tekshirish
                    return JsonResponse({"message": f"Xush kelibsiz, {user.username}"})
            return JsonResponse({"error": "Foydalanuvchi topilmadi"}, status=400)
        except sr.UnknownValueError:
            return JsonResponse({"error": "Ovoz tushunilmadi"}, status=400)
    return JsonResponse({"error": "Ovoz fayli topilmadi"}, status=400)
