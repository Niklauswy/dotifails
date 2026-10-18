"""Ephemeral PulseAudio meters: raw samples stay in memory, never recorded."""
from PySide6.QtCore import QProcess,Signal
from PySide6.QtWidgets import QProgressBar
import array,math

class AudioMeter(QProgressBar):
    def __init__(self,parent=None):
        super().__init__(parent);self.setRange(0,100);self.setValue(0);self.setFormat('— dBFS')
        self.process=QProcess(self);self.process.readyReadStandardOutput.connect(self.samples)
        self.process.errorOccurred.connect(lambda _:self.setFormat('parec no disponible'))
        self.gain=1
    def start(self,device,gain):
        self.stop();self.gain=gain
        if device:self.process.start('parec',['--raw','--format=s16le','--rate=8000','--channels=1','--latency-msec=100','--device='+device])
    def samples(self):
        raw=bytes(self.process.readAllStandardOutput());values=array.array('h');values.frombytes(raw[:len(raw)//2*2])
        if not values:return
        peak=max(abs(v) for v in values)/32768*self.gain;db=20*math.log10(max(peak,.000001))
        self.setValue(round(max(0,min(100,(db+60)/60*100))));self.setFormat(f'{db:.0f} dBFS'+(' · pico' if peak>=.98 else ''))
    def stop(self):
        if self.process.state()!=QProcess.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(400):self.process.kill();self.process.waitForFinished(400)
        self.setValue(0);self.setFormat('— dBFS')
