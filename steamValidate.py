import os
import re
import time
import vdf
import json
import winreg
import win32api
import locale
import datetime
from datetime import datetime as dt


ruLocale={"steamError":"Ошибка поиска Steam",
          "finished1":'Работа завершена: время {time}, всего игр {total}, пропущено {alreadyProcessed}, ошибок пути {folderErrors}.',
          "finished2":"проверка завершена",
          "finishedErr":"ошибка проверки",
          "skip":"Пропуск {name} : {size} Гб : {app_id} : {installdir}, уже в списке завершенного.",
          "start":"Запуск проверки {name} : {size} Гб : {app_id} : {installdir}, ожидаю завершения.",
        }
enLocale={"steamError":"Steam detect error",
          "finished1":'Work done: time {time}, total games {total}, skipped {alreadyProcessed}, path errors {folderErrors}.',
          "finished2":"check done",
          "finishedErr":"check error",
          "skip":"skip {name} : {size} Gb : {app_id} : {installdir}, marked already checked today.",
          "start":"start check {name} : {size} Gb : {app_id} : {installdir}, waiting.",
          }

def formatTime(elapsed_time):
    if elapsed_time < 3600:
        minutes, seconds = divmod(elapsed_time, 60)
        return "{:.0f}m ".format(minutes)
    elif elapsed_time < 86400:
        hours, remainder = divmod(elapsed_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        return "{:.0f}h {:.0f}m".format(hours, minutes)
    else:
        days, remainder = divmod(elapsed_time, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        return "{:.0f}d {:.0f}h {:.0f}m".format(days, hours, minutes)


def waitForLogFile(appID, filePosition):
    currentLogSize = os.path.getsize(logFilename)
    while True:
        if os.path.getsize(logFilename) > currentLogSize:
            with open(logFilename, 'r') as log_file:
                log_file.seek(filePosition)
                for line in log_file:
                    logMatch = re.search(
                        r'.+AppID '+str(appID)+' scheduler finished : removed from schedule \(result (.+),.+\)', line,re.IGNORECASE)
                    logMatch2 = re.search(
                        r'.+AppID '+str(appID)+' is marked "NoUpdatesAfterInstall" - (skipping validation)', line,re.IGNORECASE)
                    if logMatch:
                        result = logMatch.group(1)
                        return result
                    elif logMatch2:
                        result = logMatch2.group(1)
                        return result
                currentLogSize = os.path.getsize(logFilename)
                filePosition = currentLogSize
        elif os.path.getsize(logFilename) < currentLogSize:
            currentLogSize=0
        time.sleep(0.5)

def ProcessSteamFolder(directory):

    global current

    for filename in os.listdir(directory):
        if filename.endswith('.acf'):

            filepath = os.path.join(directory, filename)

            with open(filepath, 'r') as f:
                acf_data = vdf.load(f)

                app_id = acf_data['AppState']['appid']
                name = acf_data['AppState']['name']
                size=round(float(acf_data["AppState"]['SizeOnDisk'])/pow(2,30),2)
                installdir = '"' + \
                    os.path.join(directory, 'common',
                                 acf_data['AppState']['installdir'])+'"'

                ctime = dt.now()
                ftime= f'{ctime.hour:02}:{ctime.minute:02}'

                if app_id in finishedData:
                    print(
                        f'{current:02}/{total:02} {ftime} '+currentLocale['skip'].format(name=name,app_id=app_id,installdir=installdir,size=size))
                else:
                    print(
                        f'{current:02}/{total:02} {ftime} '+ currentLocale['start'].format(name=name,app_id=app_id,installdir=installdir,size=size))    

                    cmd = f'/c start steam://validate/{app_id}'

                    filePosition = os.path.getsize(logFilename)

                    win32api.ShellExecute(0, "open", 'cmd.exe', cmd, "", 1)

                    result = waitForLogFile(app_id, filePosition)
                    if result=="No Error":
                        ctime = dt.now()
                        ftime= f'{ctime.hour:02}:{ctime.minute:02}'

                        print(
                            f"{current:02}/{total:02} {ftime} {currentLocale['finished2']} {name} : {app_id} : {installdir}, {result}.")

                        finishedData[app_id] = name

                        if storeFinished:
                            try:
                                with open(finishedPath, 'w') as f:
                                    json.dump(finishedData, f, indent=4)
                            except:
                                pass
                    else:
                        print(
                            f"{current:02}/{total:02} {ftime} {currentLocale['finishedErr']} {name} : {app_id} : {installdir}, {result}.")

                    time.sleep(20)

                current += 1


storeFinished = True

currentLocale=enLocale
if "Russian_Russia" in locale.getlocale():
    currentLocale=ruLocale

try:
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,"SOFTWARE\\WOW6432Node\\Valve\\Steam")
    steamFolder = winreg.QueryValueEx(key, "InstallPath")[0]
except:
    steamFolder=None

if steamFolder is not None and os.path.isdir(steamFolder):
    logFilename = os.path.join(steamFolder, "logs", "content_log.txt")

    currentDate = datetime.date.today().strftime("%Y-%m-%d")
    finishedPath = f"finished-{currentDate}.json"
    finishedData = {}

    if storeFinished:
        try:
            with open(finishedPath, 'r') as f:
                finishedData = json.load(f)
        except:
            pass

    alreadyProcessed = len(finishedData)

    folderErrors = 0
    total = 0
    current = 1
    startTime = time.time()

    steamFolders=[]
    with open(os.path.join(steamFolder,"steamapps","libraryfolders.vdf"), 'r') as f:
        steamLibraries=vdf.load(f)
        for key in steamLibraries['libraryfolders'].keys():
            library=os.path.join(steamLibraries['libraryfolders'][key]['path'],"steamapps")
            steamFolders.append(library)
        for folder in steamFolders:
            if os.path.isdir(folder):
                for filename in os.listdir(folder):
                    if filename.endswith('.acf'):
                        total += 1
        for folder in steamFolders:
            if os.path.isdir(folder):
                ProcessSteamFolder(folder)
            else:
                folderErrors += 1

    endTime = time.time()
    elapsedTime = endTime - startTime

    print(currentLocale['finished1'].format(time=formatTime(elapsedTime),total=len(finishedData),alreadyProcessed=alreadyProcessed,folderErrors=folderErrors))
else:
    print(currentLocale['steamError'])