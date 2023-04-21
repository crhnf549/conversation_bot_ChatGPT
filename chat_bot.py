import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
from pydub import AudioSegment
from pydub.silence import split_on_silence
from win32com.client import constants
import win32com.client
import pythoncom
import openai
import pyaudio
import keyboard
import time
import winsound

# グローバル変数初期化
hearing_flag = 0 # ユーザーの音声が聞こえるかどうかを判断するフラグ
voicing_flag = 0 # ChatGPTが話し中かどうか判断するフラグ
recognizing_flag = 0 # ユーザーの話した内容を解析中かどうかを判断するフラグ
thinking_flag = 0 # 話したい内容考えて話し出すまで待っている状態かを判断するフラグ
end_flag = 0 # プログラム終了を指示するフラグ

mode = 0 # 1:音声入力モード 2:キーボード入力モード 3:状態表示モード
audio_input = 0
keyboard_input = 1
display_state = 2

threshold = 0.05 # 音声の閾値を設定
silence_counter = 0 # 無音時間計測カウンターを初期化
silence_frames = 44100 * 2 # 無音の時間が3秒に相当するフレーム数を設定
user_text = '' # ユーザーが直近に話した内容

fs = 44100 # サンプリングレート
duration = 30 # 録音時間（秒）
chunk = 30 # 保存するチャンクの長さ（秒）

# バッファとカウンターの初期化
buffer = np.zeros((fs * chunk * 2, 1))
counter = 0

# Pyaudioによってコールバックされる関数
def get_state(in_data, frame_count, time_info, status):
    global hearing_flag
    global recognizing_flag
    global end_flag
        
    global mode
    
    global silence_counter
    global silence_frames
    global threshold
    
    # 音声データをnumpy配列に変換
    data = np.frombuffer(in_data, dtype=np.float32)
    # 音声データの振幅の平均値を計算
    amplitude = np.mean(np.abs(data))
    #print(amplitude, threshold)
    if amplitude > threshold and mode != 2: # 振幅が閾値を超えた場合
        if hearing_flag == 0:
            hearing_flag = 1
        else: silence_counter = 0 # カウンターをリセット
    else: # 振幅が閾値以下の場合      
        if hearing_flag == 1:
            silence_counter += frame_count # カウンターにフレーム数を加算
            if silence_counter >= silence_frames: # カウンターが無音の時間に相当するフレーム数以上になった場合
                silence_counter = 0 # カウンターをリセット
                hearing_flag = 0
                recognizing_flag = 1
                
    if keyboard.is_pressed('8'):
        end_flag = 1
    elif keyboard.is_pressed("1"):
        if mode != 1:
            mode = 1
            print(f'mode={mode}')
    elif keyboard.is_pressed("2"):
        if mode != 2:
            mode = 2
            print(f'mode={mode}')
    elif keyboard.is_pressed("3"):
        if mode != 3:
            mode = 3
            print(f'mode={mode}')
    elif keyboard.is_pressed("9"):
        hearing_flag = 1
        
    if mode == 3:
        print(f'analyzing={recognizing_flag}',
            f'thinking={thinking_flag}',
            f'voicing={voicing_flag}',
            f'hearing={hearing_flag}',
            f'ending={end_flag}',
            user_text)
    
    return (in_data, pyaudio.paContinue) # 音声データと継続フラグを返す


# 文字列を読み上げる関数
def text2speech(text):
    global voicing_flag
    global hearing_flag
    
    if hearing_flag == 0:
        voicing_flag = 1
        # テキストの読み上げを開始する
        pythoncom.CoInitialize()
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Speak(text, True)
        
        # 読み上げ終了まで待つ。
        while speaker.Status.RunningState != 1 and hearing_flag == 0:
            pass
        # 読み上げ中にユーザーが話し始めたら読み上げを中止する
        speaker.Pause()
        pythoncom.CoUninitialize()
        
        voicing_flag = 0

# 録音と保存の関数を定義
def record_and_save(indata, outdata, frames, time, status):
    global buffer
    global fs
    # バッファに入力データを追加
    buffer = np.roll(buffer, -frames, axis=0)
    buffer[-frames:, :] = indata
    # バッファの最新のチャンクをwavファイルに保存
    filename = f'./desktop/recorded.wav' # timeモジュールをtmとして呼び出す
    sf.write(filename, buffer[-fs * chunk:, :], fs)
    

    #print(f'Saved {filename}')

def speech2text():
    global recognizing_flag
    global thinking_flag
    global end_flag
    global mode
    global user_text
    
    while end_flag == 0:
        if mode != 2 and recognizing_flag == 1:
            if mode == 1:
                print('\n[あなた]')
                print(" >> Recognizing what you said...")
                # 聞き終わったことを知らせる音を鳴らす
                winsound.Beep(500, 250) # 500Hzの音を250ms鳴らす
            # 音声ファイルを読み込む
            sound = AudioSegment.from_file("./desktop/recorded.wav")

            # 無音区間で分割する
            chunks = split_on_silence(
                sound,
                min_silence_len=2000, # 無音と判定する最小の長さ（ミリ秒）
                silence_thresh=-40, # 無音と判定する閾値（dB）
                keep_silence=100 # 分割後のチャンクに残す無音の長さ（ミリ秒）
            )
            
            # chunksが空でない場合のみ処理を行う
            if len(chunks)>=1:
                # 分割されたチャンクのリストから最後の要素を取り出す
                last_chunk = chunks[-1]

                # NumPy配列に変換する
                data = last_chunk.get_array_of_samples()
                data = np.array(data).reshape(-1, last_chunk.channels)

                # サンプリングレートを取得する
                sr = last_chunk.frame_rate

                # 音声ファイルとして保存する
                sf.write(f'./desktop/split.wav', data, sr)
                
                # 音声データを開く
                audio_file = open('./desktop/split.wav', 'rb')

                # Whisper APIのエンドポイントにリクエストを送信
                transcript = openai.Audio.transcribe("whisper-1", audio_file, language="Ja")
                
                # 文字列化されたテキストを出力
                user_text = str(transcript["text"])
                if mode == 1: print(user_text)

                thinking_flag = 1
                
            recognizing_flag = 0
        else: time.sleep(.1)
    
    

def chat_gpt():
    global thinking_flag
    global user_text
    global mode
    if thinking_flag == 1:
        # ユーザーからの発話内容を会話履歴に追加
        user_action = {"role": "user", "content": user_text}
        conversationHistory.append(user_action)
        
        # 応答内容をコンソール出力
        if mode != 3:
            print("[ChatGPT]")
            print(" >> Thinking response...")
            
        res = chat(conversationHistory)
        
        # ChatGPTからの応答内容を会話履歴に追加
        chatGPT_responce = {"role": "assistant", "content": res}
        conversationHistory.append(chatGPT_responce)
        thinking_flag = 0
        
# ChatGPTからの返答を出力する関数
def chat(covnversationHistory):
    global voicing_flag
    global hearing_flag
    global end_flag
    global user_text
    global mode
    
    # ストリーミングされたテキストを処理する変数
    fullResponse = ""
    RealTimeResponce = ""   

    # APIリクエストを作成する
    response = openai.ChatCompletion.create(
        messages=conversationHistory,
        max_tokens=1024,
        n=1,
        stream=True,
        temperature=0.5,
        stop=None,
        presence_penalty=0.5,
        frequency_penalty=0.5,
        model="gpt-3.5-turbo"
    )
    
    # 会話終了という発言が含まれていたら終了フラグを立てる
    if '会話終了' in user_text: end_flag = 1 
    
    # APIリクエストを送ったら直近の発言内容を削除
    user_text = ''

    for chunk in response:
        text = chunk['choices'][0]['delta'].get('content')

        if(text==None):
            pass
        else:
            if hearing_flag == 1:
                print('\n>> Canceled.\n')
                break

            fullResponse += text
            RealTimeResponce += text

            # 部分的なレスポンスを随時表示していく
            if mode != 3: print(text, end='', flush=True)
            
            target_char = ["。", "！", "？", "\n"]
            for index, char in enumerate(RealTimeResponce):
                if char in target_char and voicing_flag == 0:
                    # 1文完成ごとにテキストを読み上げる(遅延時間短縮のため)
                    pos = index + 1
                    sentence = RealTimeResponce[:pos]
                    RealTimeResponce = RealTimeResponce[pos:]
                    thread = threading.Thread(target=text2speech, args=(sentence,))
                    thread.start()
                elif hearing_flag == 1: break 
                    
    # 残りの文章を読み上げる
    while True:
        if voicing_flag == 0:
            thread = threading.Thread(target=text2speech, args=(RealTimeResponce,))
            thread.start()    
            break
        elif hearing_flag == 1: break

    # APIからの完全なレスポンスを返す
    return fullResponse
        

#####################
# OpenAI APIの初期化 #
#####################
openai.api_key = ""


conversationHistory = [] # UserとChatGPTとの会話履歴を格納するリスト
setting = {"role": "system", "content": "あなたは人間の友達です。できるだけ句点を多く含めて返答を返してください。"}
conversationHistory.append(setting)

##################
# Pyaudioを初期化 #
##################
p = pyaudio.PyAudio() # PyAudioオブジェクトを作成
stream = p.open(format=pyaudio.paFloat32, channels=1, rate=fs, frames_per_buffer=4410, input=True, stream_callback=get_state) # ストリームオブジェクトを作成
stream.start_stream() # ストリームを開始

# Streamオブジェクトの作成（blocksize=0とlatency=0を指定）
sd_stream = sd.Stream(samplerate=fs,blocksize=4410,latency=0,channels=1,callback=record_and_save)
sd_stream.start()

#stop_event = threading.Event()
thread_listening = threading.Thread(target=speech2text, args=())
thread_listening.start()

print('Started conversation...')
while True:
    if mode == 2 and thinking_flag == 0:
        user_text = input('\n[あなた]\n')
        thinking_flag = 1
        
    if end_flag == 1:
        thread_listening.join()
        # ストリームを終了
        stream.close()
        sd_stream.stop()
        break
    chat_gpt()
    time.sleep(.1)
    

            
        
