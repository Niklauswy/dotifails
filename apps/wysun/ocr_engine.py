"""Local OCR independent of the graphical session's PATH."""
import os,shutil,subprocess
from pathlib import Path
from PySide6.QtCore import Qt,QByteArray,QBuffer,QIODevice
from PySide6.QtGui import QImage,QPainter,QColor
from core import sensitive

ENGINE_VERSION=2

def tesseract_binary():
    # The user-level launcher also sets up the portable language/library bundle.
    local=Path.home()/'.local/bin/tesseract'
    return str(local) if local.is_file() and os.access(local,os.X_OK) else shutil.which('tesseract')

def image_bytes(image):
    data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly);image.save(buffer,'PNG');return bytes(data)

def prepared_image(image):
    result=QImage(image.size(),QImage.Format_RGB32);result.fill(QColor('white'))
    painter=QPainter(result);painter.drawImage(0,0,image);painter.end()
    # Small UI text benefits from scaling; keep large screenshots legible and bounded.
    edge=max(result.width(),result.height())
    factor=min(2.,3200/max(1,edge))
    if factor!=1:result=result.scaled(round(result.width()*factor),round(result.height()*factor),Qt.KeepAspectRatio,Qt.SmoothTransformation)
    sample=result.scaled(48,48,Qt.IgnoreAspectRatio,Qt.FastTransformation)
    luminance=sum(sample.pixelColor(x,y).lightness() for x in range(48) for y in range(48))/2304
    if luminance<105:result.invertPixels()
    bordered=QImage(result.width()+20,result.height()+20,QImage.Format_RGB32);bordered.fill(QColor('white'))
    painter=QPainter(bordered);painter.drawImage(10,10,result);painter.end();return bordered

def recognize(image):
    meta={'ocr_engine':ENGINE_VERSION,'ocr_status':'no disponible','ocr_error':''}
    binary=tesseract_binary()
    if image.isNull():meta['ocr_error']='imagen no compatible';return '',meta
    if not binary:meta['ocr_error']='Tesseract no está instalado';return '',meta
    data=image_bytes(prepared_image(image));env=dict(os.environ,OMP_THREAD_LIMIT='1');text=''
    try:
        for mode in ('11','6'):
            priority=[shutil.which('nice'),'-n','15'] if shutil.which('nice') else []
            result=subprocess.run(priority+[binary,'stdin','stdout','-l','spa+eng','--psm',mode,'--dpi','300'],input=data,capture_output=True,env=env,timeout=18)
            if result.returncode:
                meta['ocr_error']='No se pudo iniciar el motor o cargar sus idiomas';return '',meta
            text=result.stdout.decode('utf-8',errors='replace').strip()[:30000]
            if text:break
        if sensitive(text):meta.update(ocr_status='protegido',ocr_error='Texto excluido por la protección de datos sensibles');return '',meta
        meta['ocr_status']='listo' if text else 'sin texto';return text,meta
    except subprocess.TimeoutExpired:meta['ocr_error']='El reconocimiento tardó demasiado'
    except (OSError,subprocess.SubprocessError):meta['ocr_error']='No se pudo ejecutar Tesseract'
    return '',meta
