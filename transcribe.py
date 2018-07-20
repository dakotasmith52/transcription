import speech_recognition as sr
import boto3

s3 = boto3.resource('s3')
r = sr.Recognizer()

def transcribe():
    recording = sr.AudioFile('me.wav')
    with recording as source:
        audio = r.record(source)
    print(r.recognize_google(audio))


