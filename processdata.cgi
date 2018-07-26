#!/usr/bin/python

import cgi
import boto3
from random import randint
import time
import os
import json
import urllib2
from tempfile import gettempdir
import io
from contextlib import closing
import sys
import shutil
import speech_recognition as sr
from pydub import AudioSegment
import subprocess

formData = cgi.FieldStorage()
s3 = boto3.resource('s3')
transcript = ''
translation = ''
outfile = ''
fileitem = formData['uploadfile']
translationfile='translation.txt'
transcriptionfile='transcription.txt'
output = ''
def last(int, string):
    myformat = string[(-1)*int:]
    return myformat

def determineFormat():
    f = outfile
    if last(4,f) == 'flac':
        return 'flac'
    else:
        return str(last(3,f))

def upload(name,key):
    s3.meta.client.upload_file(name, 'rainbowbird', key+name)

def uploadformfile(bucketname):
    """This saves a file uploaded by an HTML form.
       The form_field is the name of the file input field from the form.
       For example, the following form_field would be "file_1":
           <input name="file_1" type="file">
       The upload_dir is the directory where the file will be written.
       If no file was uploaded or if the field does not exist then
       this does nothing.
    """

    if not fileitem.file: print('<h1>error</h1>')

    global outfile
    outfile = fileitem.filename
    with io.FileIO(outfile, 'wb') as fout:
        shutil.copyfileobj(fileitem.file, fout, 100000)
    s3 = boto3.resource('s3')
    s3.meta.client.upload_file(outfile, bucketname, 'recordings/'+outfile)

def convert_audio():
    sound = AudioSegment.from_file(outfile)
    if determineFormat() == 'mp4':
        command = "ffmpeg -i "+outfile+' -ab 160k -ac 2 -ar 44100 -vn converted_audio.wav'
        subprocess.call(command, shell=True)
    else:
        converted_file = sound.export('./converted_audio.wav', format='wav')

def transcribe(inputLang):
    convert_audio()
    r = sr.Recognizer()
    recording = 'converted_audio.wav'
    with recording as source:
        audio = r.record(source)
    global transcript
    transcript = r.recognize_google(audio, language=inputLang)
    with open('transcription.txt', 'w') as x:
        x.write(transcript)
    upload('transcription.txt', 'transcriptions/')
    os.remove(outfile)

    
def translate(inputLang, outputLang, transcription):
    text=transcription
    translate=boto3.client(service_name='translate', region_name='us-west-2')
    result=translate.translate_text(Text=text,
                SourceLanguageCode=determineSource_targetlangcode(inputLang), TargetLanguageCode=outputLang)
    translatedText=result.get('TranslatedText').encode('utf-8')
    with open('translation.txt', 'w') as x:
        x.write(translatedText)
    upload('translation.txt', 'translations/')
    global translation
    translation = translatedText

def determineSource_targetlangcode(inputLang):
    langlib = {'en-US':'en', 'es-US':'es'}
    return langlib[inputLang] if inputLang in langlib else None

def polly(lang, text):
    polly=boto3.client(service_name='polly', region_name='us-west-2')
    response = polly.synthesize_speech(Text=text, OutputFormat="mp3",
                                        VoiceId=determineVoice(lang))
    if "AudioStream" in response:
    # Note: Closing the stream is important as the service throttles on the
    # number of parallel connections. Here we are using contextlib.closing to
    # ensure the close method of the stream object will be called automatically
    # at the end of the with statement's scope.
        with closing(response["AudioStream"]) as stream:
	    global output
            output = str(randint(0, 9999)) + lang + '.mp3'

            try:
                # Open a file for writing the output as a binary stream
                with io.FileIO(output, "wb") as file:
                    file.write(stream.read())
            except IOError as error:
                # Could not write to file, exit gracefully
                print(error)
                sys.exit(-1)
    else:
        # The response didn't contain audio data, exit gracefully
        print("Could not stream audio")
        sys.exit(-1)
    upload(output, 'speech/')

def determineVoice(lang):
    pollyVoice = {'en-US': 'Amy', 'en': 'Amy', 'fr': 'Celine', 'de': 'Vicki', 'pt': 'Vitoria','es': 'Enrique', 'es-US':'Enrique'}
    return pollyVoice[lang] if lang in pollyVoice else None

def genSignedUrl(key_name):
    s3 = boto3.client('s3')
    signedUrl = s3.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': 'rainbowbird',
            'Key': key_name
        }
    )
    return signedUrl

def getAudioUrl():
    if checkAudio():
	print("<div class='Audio'>")
	print("    <a href="+genSignedUrl("speech/"+output)+">Click here</a> to download your audio file.<br>")
	print("</div>")
    else:
	return

def getTranslateUrl():
    if checkTranslate():
	print("<div class='Transcription'>")
        print("<a href="+genSignedUrl("translations/"+translationfile)+">Click here</a> to download your translated text file.<br>")
	print("</div>")
    else:
	return

def getTranscribeUrl():
    if checkTranscript():
	print("<div class='Text'>")
	print("<a href="+genSignedUrl("transcriptions/"+transcriptionfile)+">Click here</a> to download your transcription file.<br>")
	print("</div>")
    else:
	return

def htmlTop():
    print("""Content-type:text/html\n\n
    <!DOCTYPE html>
    <html lang='en'>
        <head>
	    <meta charset='utf-8'/>
            <title>Rainbow Bird - Results</title>
            <meta http-equiv='Content-Type' content='text/html' charset='UTF-8'>
            <meta name='viewport' content='width=device-width, initial-scale=1.0'>
            <!-- STYLE -->
	    <link rel='stylesheet' href='https://s3-us-west-2.amazonaws.com/rainbowbird/webstuff/reset.css' />
            <link type='text/css' rel='stylesheet' href='https://s3-us-west-2.amazonaws.com/rainbowbird/webstuff/resultsstyles.css' />
            <link rel='stylesheet' href='https://fonts.googleapis.com/css?family=Montserrat' />
            <link type='text/css' rel='stylesheet' href='https://s3-us-west-2.amazonaws.com/rainbowbird/webstuff/animation.css' />
        </head>
        <body>
	    <h1>Rainbow Bird</h1>
	    <div class='line'></div>
	    <h2>Audio & Video Transcription</h2>
""")

def htmlTail():
    print("""<div class='home'><a class='index' href='http://www.rosettasparrot.com'>Home</a></div>
	<ul class='bg-bubbles'>
            <li></li>
            <li></li>
            <li></li>
            <li></li>
            <li></li>
            <li></li>
            <li></li>
            <li></li>
            <li></li>
            <li></li>
            <li></li>
        </ul>
	</body>
    </html>""")

def getFile():
    myfile = formData['uploadfile']
    myfilename = myfile.filename
    return myfilename

def getFromLang():
    fromLanguage = formData.getvalue('fromLanguage')
    return fromLanguage

def getToLang():
    toLanguage = formData.getvalue('toLanguage')
    if checkTranslate():
        return toLanguage
    else:
        return None

def doTranslate(inputLang, outputLang, transcript):
    if checkTranslate() == False:
	return None
    elif checkTranslate() and translation != '':
        return translation
    elif checkTranslate() and translation == '':
        return translate(inputLang, outputLang, doTranscript(inputLang))
    elif checkTranslate() == False:
        return
    else:
        return

def doTranscript(inputLang):
    if transcript == '':
	if checkTranscript():
	    transcribe(inputLang)
    	elif checkAudio():
	    transcribe(inputLang)
	elif checkTranslate():
	    transcribe(inputLang)
	else:
	    pass
    elif transcript != '':
	return transcript
    elif checkTranscript():
        if transcript != '':
            return transcript
	else:
	    pass
    elif checkTranscript():
	if transcript == '':
            return transcribe(inputLang)
	else:
	    pass
    elif checkTranscript() == False:
        return
    else:
        return

def doAudio(inputLang, outputLang, transcript, translation):
    if checkAudio() == False:
	return
    elif checkAudio() and checkTranscript() and checkTranslate():
        polly(inputLang, doTranscript(inputLang))
	polly(outputLang, doTranslate(inputLang, outputLang, transcript))
        return
    elif checkAudio() and checkTranslate():
        polly(outputLang, translation)
        return
    elif checkAudio() and checkTranscript():
        polly(inputLang, doTranscript(inputLang))
        return
    elif checkAudio():
        return polly(inputLang, doTranscript(inputLang))
    else:
        return

def checkTranslate():
    translation = formData.getvalue('translate')
    return translation

def checkAudio():
    audio = formData.getvalue('audio')
    return audio

def checkTranscript():
    transcribe = formData.getvalue('transcript')
    return transcribe

def mainAction(fromLanguage, toLanguage):
    doTranscript(fromLanguage)
    doTranslate(fromLanguage, toLanguage, transcript)
    doAudio(fromLanguage, toLanguage, transcript, translation)
    getAudioUrl()
    getTranscribeUrl()
    getTranslateUrl()

# Main Program
if __name__ == '__main__':
    try:
        htmlTop()
        uploadformfile('rainbowbird')
        myfile = getFile()
        fromLanguage = getFromLang()
        toLanguage = getToLang()
	mainAction(fromLanguage, toLanguage)
	print('<br>')
        print('<br>')
        htmlTail()
    except:
        cgi.print_exception()
