import sys
from pathlib import Path
from collections import deque
import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QListWidget, QListWidgetItem, QSlider, QCheckBox, QSpinBox, QGroupBox, QFileDialog, QProgressBar, QColorDialog, QMessageBox, QFrame
from qt_material import apply_stylesheet

SUPPORTED={".jpg",".jpeg",".png",".webp"}
def detect_format(path):
    with open(path,"rb") as f: h=f.read(16)
    if h.startswith(b"\xff\xd8"): return "jpeg"
    if h.startswith(b"\x89PNG\r\n\x1a\n"): return "png"
    if len(h)>=12 and h[:4]==b"RIFF" and h[8:12]==b"WEBP": return "webp"
    return None
def load_image(path):
    with Image.open(path) as im: return im.convert("RGBA")
def color_mask(im,target,tolerance):
    a=np.asarray(im.convert("RGB"),dtype=np.int16); t=np.array(target,dtype=np.int16)
    return np.sqrt(np.sum((a-t)**2,axis=2))<=tolerance
def border_connected(mask):
    h,w=mask.shape; seen=np.zeros_like(mask,dtype=bool); q=deque()
    for x in range(w):
        if mask[0,x]: seen[0,x]=True;q.append((0,x))
        if mask[h-1,x] and not seen[h-1,x]: seen[h-1,x]=True;q.append((h-1,x))
    for y in range(h):
        if mask[y,0] and not seen[y,0]: seen[y,0]=True;q.append((y,0))
        if mask[y,w-1] and not seen[y,w-1]: seen[y,w-1]=True;q.append((y,w-1))
    while q:
        y,x=q.popleft()
        for ny,nx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
            if 0<=ny<h and 0<=nx<w and mask[ny,nx] and not seen[ny,nx]:
                seen[ny,nx]=True;q.append((ny,nx))
    return seen
def keep_large(mask,min_area):
    if min_area<=1:return mask
    h,w=mask.shape; seen=np.zeros_like(mask,dtype=bool); out=np.zeros_like(mask,dtype=bool)
    for y in range(h):
        for x in np.flatnonzero(mask[y] & ~seen[y]):
            if seen[y,x]:continue
            stack=[(y,int(x))];seen[y,x]=True;comp=[]
            while stack:
                cy,cx=stack.pop();comp.append((cy,cx))
                for ny,nx in ((cy-1,cx),(cy+1,cx),(cy,cx-1),(cy,cx+1)):
                    if 0<=ny<h and 0<=nx<w and mask[ny,nx] and not seen[ny,nx]:
                        seen[ny,nx]=True;stack.append((ny,nx))
            if len(comp)>=min_area:
                yy,xx=zip(*comp);out[np.array(yy),np.array(xx)]=True
    return out
def normalize(path,target,tolerance,min_area,only_border):
    im=load_image(path);mask=color_mask(im,target,tolerance)
    if only_border:mask=border_connected(mask)
    mask=keep_large(mask,min_area)
    a=np.array(im.convert("RGBA"));a[mask,:3]=np.array(target,dtype=np.uint8)
    result=Image.fromarray(a,"RGBA");out=path.with_name(path.stem+"_CLEAN"+path.suffix);fmt=detect_format(path)
    if fmt=="jpeg":result.convert("RGB").save(out,"JPEG",quality=95,optimize=True,progressive=True,exif=b"")
    elif fmt=="png":result.save(out,"PNG",optimize=True)
    elif fmt=="webp":result.save(out,"WEBP",quality=98,method=6,exif=b"",xmp=b"")
    else:raise ValueError("Formato no compatible")
    return out,int(mask.sum())

class ImageNormalizer(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle("Image Normalizer");self.resize(1180,760);self.setMinimumSize(980,650)
        self.files=[];self.target=(255,255,255);self.current_preview=None
        c=QWidget();self.setCentralWidget(c);root=QVBoxLayout(c);root.setContentsMargins(28,24,28,24);root.setSpacing(16)
        t=QLabel("Image Normalizer");t.setObjectName("title");root.addWidget(t)
        s=QLabel("Normalización y reconstrucción de áreas de color uniforme, completamente local.");s.setObjectName("subtitle");root.addWidget(s)
        top=QHBoxLayout();a=QPushButton("＋  Agregar imágenes");a.clicked.connect(self.add_files);cl=QPushButton("Limpiar lista");cl.clicked.connect(self.clear_files);top.addWidget(a);top.addWidget(cl);top.addStretch();self.counter=QLabel("0 archivos");top.addWidget(self.counter);root.addLayout(top)
        body=QHBoxLayout();body.setSpacing(18);root.addLayout(body,1)
        lb=QGroupBox("Imágenes");ll=QVBoxLayout(lb);self.list=QListWidget();self.list.currentRowChanged.connect(self.select_preview);ll.addWidget(self.list);body.addWidget(lb,2)
        right=QVBoxLayout();pb=QGroupBox("Vista previa");pl=QVBoxLayout(pb);self.preview=QLabel("Selecciona una imagen");self.preview.setAlignment(Qt.AlignCenter);self.preview.setMinimumSize(420,300);self.preview.setFrameShape(QFrame.StyledPanel);pl.addWidget(self.preview);right.addWidget(pb,1)
        cg=QGroupBox("Normalización");g=QGridLayout(cg)
        g.addWidget(QLabel("Color objetivo"),0,0);self.color_btn=QPushButton();self.color_btn.clicked.connect(self.pick_color);self.update_color_button();g.addWidget(self.color_btn,0,1)
        g.addWidget(QLabel("Tolerancia"),1,0);self.tol=QSlider(Qt.Horizontal);self.tol.setRange(0,100);self.tol.setValue(20);self.tol.valueChanged.connect(lambda v:self.tol_value.setText(str(v)));g.addWidget(self.tol,1,1);self.tol_value=QLabel("20");g.addWidget(self.tol_value,1,2)
        g.addWidget(QLabel("Área mínima (px)"),2,0);self.area=QSpinBox();self.area.setRange(1,10000000);self.area.setValue(500);self.area.setSingleStep(100);g.addWidget(self.area,2,1)
        self.border=QCheckBox("Solo regiones conectadas al borde");self.border.setChecked(True);g.addWidget(self.border,3,0,1,3)
        n=QLabel("La reconstrucción modifica únicamente los píxeles seleccionados. Los originales permanecen intactos.");n.setWordWrap(True);n.setObjectName("note");g.addWidget(n,4,0,1,3);right.addWidget(cg);body.addLayout(right,5)
        self.progress=QProgressBar();root.addWidget(self.progress);self.status=QLabel("Listo.");root.addWidget(self.status)
        run=QPushButton("NORMALIZAR IMÁGENES");run.setObjectName("primary");run.setMinimumHeight(48);run.clicked.connect(self.process);root.addWidget(run)
    def update_color_button(self):
        r,g,b=self.target;self.color_btn.setText(f"  RGB {r}, {g}, {b}  ");self.color_btn.setStyleSheet(f"background:rgb({r},{g},{b});color:{'black' if sum(self.target)>420 else 'white'};")
    def pick_color(self):
        c=QColorDialog.getColor(QColor(*self.target),self,"Seleccionar color")
        if c.isValid():self.target=(c.red(),c.green(),c.blue());self.update_color_button()
    def add_files(self):
        fs,_=QFileDialog.getOpenFileNames(self,"Seleccionar imágenes","","Imágenes (*.jpg *.jpeg *.png *.webp)")
        for f in fs:
            p=Path(f)
            if p.suffix.lower() in SUPPORTED and str(p) not in self.files:
                try:
                    if detect_format(p):self.files.append(str(p));self.list.addItem(QListWidgetItem(p.name))
                except Exception:pass
        self.counter.setText(f"{len(self.files)} archivos")
        if self.files and self.list.currentRow()<0:self.list.setCurrentRow(0)
    def clear_files(self):
        self.files.clear();self.list.clear();self.counter.setText("0 archivos");self.preview.clear();self.status.setText("Listo.")
    def select_preview(self,row):
        if row<0 or row>=len(self.files):return
        try:self.current_preview=QPixmap(self.files[row]);self.update_preview()
        except Exception:self.preview.setText("No se pudo mostrar la imagen.")
    def resizeEvent(self,e):super().resizeEvent(e);self.update_preview()
    def update_preview(self):
        if self.current_preview and not self.current_preview.isNull():self.preview.setPixmap(self.current_preview.scaled(self.preview.size()-QSize(12,12),Qt.KeepAspectRatio,Qt.SmoothTransformation))
    def process(self):
        if not self.files:QMessageBox.information(self,"Image Normalizer","Agrega al menos una imagen.");return
        self.progress.setMaximum(len(self.files));self.progress.setValue(0);ok=0;errors=[]
        for i,f in enumerate(self.files,1):
            try:
                out,pix=normalize(Path(f),self.target,self.tol.value(),self.area.value(),self.border.isChecked());ok+=1;self.status.setText(f"{Path(f).name} → {out.name} · {pix:,} píxeles normalizados")
            except Exception as e:errors.append(f"{Path(f).name}: {e}")
            self.progress.setValue(i);QApplication.processEvents()
        msg=f"Proceso terminado. {ok} de {len(self.files)} imágenes procesadas.\n\nLas copias se guardaron junto al original con el sufijo _CLEAN."
        if errors:msg+="\n\nErrores:\n"+"\n".join(errors[:8])
        QMessageBox.information(self,"Image Normalizer",msg)

if __name__=="__main__":
    app=QApplication(sys.argv);apply_stylesheet(app,theme="dark_teal.xml",invert_secondary=True)
    app.setStyleSheet(app.styleSheet()+"""QLabel#title{font-size:28px;font-weight:700;}QLabel#subtitle{color:#aeb7bd;font-size:13px;}QLabel#note{color:#9aa6ad;font-size:11px;}QPushButton#primary{font-size:14px;font-weight:700;padding:8px;}""")
    win=ImageNormalizer();win.show();sys.exit(app.exec())
