import os, sys, struct, ctypes, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

SUPPORTED = {'.jpg', '.jpeg', '.png', '.webp'}

def clean_jpeg(data):
    if not data.startswith(b'\xff\xd8'):
        raise ValueError('JPEG inválido')
    out = bytearray(data[:2]); i = 2; removed = []
    while i < len(data):
        if data[i] != 0xFF:
            out.extend(data[i:]); break
        while i < len(data) and data[i] == 0xFF:
            i += 1
        if i >= len(data): break
        marker = data[i]; i += 1
        if marker == 0xD9:
            out.extend(b'\xff\xd9'); break
        if marker == 0xDA:
            out.extend(b'\xff\xda'); out.extend(data[i:]); break
        if marker == 0xD8 or 0xD0 <= marker <= 0xD7:
            out.extend(b'\xff' + bytes([marker])); continue
        if i + 2 > len(data): raise ValueError('JPEG truncado')
        ln = struct.unpack('>H', data[i:i+2])[0]
        if ln < 2 or i + ln > len(data): raise ValueError('JPEG truncado')
        segment = data[i:i+ln]; payload = segment[2:]
        remove = False; why = None

        # Remove common metadata/provenance containers before SOS.
        if marker == 0xFE:
            remove, why = True, 'COM'
        elif marker == 0xE1:
            low = payload.lower()
            if payload.startswith(b'Exif\x00\x00'):
                remove, why = True, 'EXIF'
            elif b'xmp' in low or b'http://ns.adobe.com/xap/1.0/' in low:
                remove, why = True, 'XMP'
            elif b'c2pa' in low or b'jumbf' in low:
                remove, why = True, 'C2PA'
        elif marker == 0xED:
            remove, why = True, 'IPTC/Photoshop'
        elif marker == 0xEB and (b'c2pa' in payload.lower() or payload[:4] == b'JP\x00\x00'):
            remove, why = True, 'C2PA/JUMBF'
        elif marker == 0xE4 and b'c2pa' in payload.lower():
            remove, why = True, 'C2PA'
        elif marker == 0xE2 and (b'icc_profile' in payload.lower() or b'c2pa' in payload.lower()):
            # Privacy-first mode removes ICC as well as C2PA when present.
            remove, why = True, 'ICC/C2PA'

        if remove:
            removed.append(why)
        else:
            out.extend(b'\xff' + bytes([marker]) + segment)
        i += ln
    return bytes(out), removed

def clean_png(data):
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('PNG inválido')
    out = bytearray(data[:8]); i = 8; removed = []
    while i + 12 <= len(data):
        ln = struct.unpack('>I', data[i:i+4])[0]
        typ = data[i+4:i+8]
        end = i + 12 + ln
        if end > len(data): raise ValueError('PNG truncado')
        chunk = data[i:end]
        if typ in (b'tEXt', b'zTXt', b'iTXt', b'eXIf', b'iCCP'):
            removed.append(typ.decode('latin1'))
        else:
            out.extend(chunk)
        i = end
        if typ == b'IEND': break
    return bytes(out), removed

def clean_webp(data):
    if not data.startswith(b'RIFF') or data[8:12] != b'WEBP':
        raise ValueError('WebP inválido')
    out = bytearray(data[:12]); i = 12; removed = []
    while i + 8 <= len(data):
        typ = data[i:i+4]; ln = struct.unpack('<I', data[i+4:i+8])[0]
        end = i + 8 + ln + (ln & 1)
        if end > len(data): raise ValueError('WebP truncado')
        payload = data[i+8:i+8+ln]
        if typ in (b'EXIF', b'XMP ', b'ICCP'):
            removed.append(typ.decode('latin1').strip())
        elif typ == b'JUMD' or b'c2pa' in payload.lower():
            removed.append('C2PA')
        else:
            out.extend(data[i:end])
        i = end
    out[4:8] = struct.pack('<I', len(out)-8)
    return bytes(out), removed

def detect_format(data, path):
    if data.startswith(b'\x89PNG\r\n\x1a\n'): return 'png'
    if data.startswith(b'\xff\xd8'): return 'jpeg'
    if len(data) >= 12 and data.startswith(b'RIFF') and data[8:12] == b'WEBP': return 'webp'
    return path.suffix.lower().lstrip('.') or 'desconocido'

def structural_clean(path):
    data = path.read_bytes()
    fmt = detect_format(data, path)
    if fmt == 'jpeg': clean, removed = clean_jpeg(data)
    elif fmt == 'png': clean, removed = clean_png(data)
    elif fmt == 'webp': clean, removed = clean_webp(data)
    else: raise ValueError(f'Formato no reconocido (extensión: {path.suffix or "sin extensión"})')
    out = path.with_name(path.stem + '_CLEAN' + path.suffix)
    out.write_bytes(clean)
    return out, removed, len(data), len(clean)

def normalized_reencode(path):
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError('Falta Pillow. Ejecuta BUILD_SUNE.bat para reconstruir la versión portable.')
    with Image.open(path) as im:
        fmt = detect_format(path.read_bytes(), path)
        out = path.with_name(path.stem + '_CLEAN' + path.suffix)
        # Convert only when needed for safe JPEG output.
        if fmt == 'jpeg':
            if im.mode not in ('RGB', 'L'):
                im = im.convert('RGB')
            im.save(out, format='JPEG', quality=95, optimize=True, progressive=True, exif=b'')
        elif fmt == 'png':
            if im.mode == 'P':
                im = im.convert('RGBA')
            im.save(out, format='PNG', optimize=True)
        elif fmt == 'webp':
            if im.mode not in ('RGB', 'RGBA'):
                im = im.convert('RGBA' if 'A' in im.getbands() else 'RGB')
            im.save(out, format='WEBP', quality=98, method=6, exif=b'', xmp=b'')
        else:
            raise ValueError('Formato no compatible con normalización')
    return out

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('MetaDataCleaner')
        self.geometry('850x610')
        self.minsize(760,520)
        self.files=[]

        style=ttk.Style(self)
        style.configure('Title.TLabel', font=('Segoe UI',20,'bold'))
        style.configure('Sub.TLabel', font=('Segoe UI',10))

        root=ttk.Frame(self,padding=20)
        root.pack(fill='both',expand=True)

        ttk.Label(root,text='METADATACLEANER',style='Title.TLabel').pack(anchor='w')
        ttk.Label(
            root,
            text='Limpieza local de metadata y normalización opcional de imágenes.',
            style='Sub.TLabel'
        ).pack(anchor='w',pady=(2,16))

        bar=ttk.Frame(root)
        bar.pack(fill='x')
        ttk.Button(bar,text='＋ Agregar imágenes',command=self.add).pack(side='left')
        ttk.Button(bar,text='Limpiar lista',command=self.clear).pack(side='left',padx=8)
        self.count=ttk.Label(bar,text='0 archivos')
        self.count.pack(side='right')

        self.listbox=tk.Listbox(root,height=12,selectmode='extended',font=('Consolas',10))
        self.listbox.pack(fill='both',expand=True,pady=12)

        opts=ttk.LabelFrame(root,text='Modo de procesamiento',padding=10)
        opts.pack(fill='x')
        self.mode=tk.StringVar(value='reencode')
        ttk.Label(
            opts,
            text='Normalizar / re-encode — crea una copia nueva de la imagen sin metadata.',
            font=('Segoe UI',10,'bold')
        ).pack(anchor='w')
        ttk.Label(
            opts,
            text='La imagen se vuelve a guardar localmente para eliminar metadata y generar una representación nueva.',
            foreground='#555'
        ).pack(anchor='w',pady=(5,0))

        self.progress=ttk.Progressbar(root,mode='determinate')
        self.progress.pack(fill='x',pady=(14,5))
        self.status=ttk.Label(root,text='Listo.')
        self.status.pack(anchor='w')
        ttk.Button(
            root,text='🧹 LIMPIAR ARCHIVOS',command=self.clean
        ).pack(fill='x',pady=(12,0),ipady=7)

        # Apply the Windows icon after the real window has been created.
        self.after(50, self._set_app_icon)
        self.after(500, self._set_app_icon)

    def _set_app_icon(self):
        try:
            base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
            ico = base / 'MCr.ico'
            png = base / 'MCr_logo.png'

            if ico.exists():
                self.iconbitmap(default=str(ico))
            if png.exists():
                # Keep a persistent PhotoImage reference.
                self._app_icon = tk.PhotoImage(file=str(png))
                self.iconphoto(True, self._app_icon)

            if sys.platform.startswith('win') and ico.exists():
                self.update_idletasks()
                user32 = ctypes.windll.user32
                hwnd = int(self.winfo_id())
                WM_SETICON = 0x0080
                ICON_SMALL = 0
                ICON_BIG = 1
                IMAGE_ICON = 1
                LR_LOADFROMFILE = 0x00000010

                ico_path = str(ico.resolve())
                hbig = user32.LoadImageW(None, ico_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
                hsmall = user32.LoadImageW(None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

                if hbig:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hbig)
                if hsmall:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hsmall)

                SWP_NOSIZE = 0x0001
                SWP_NOMOVE = 0x0002
                SWP_NOZORDER = 0x0004
                SWP_FRAMECHANGED = 0x0020
                user32.SetWindowPos(
                    hwnd, 0, 0, 0, 0, 0,
                    SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED
                )

                self._mcr_hicon_big = hbig
                self._mcr_hicon_small = hsmall
        except Exception as e:
            self._icon_error = str(e)

    def add(self):
        fs=filedialog.askopenfilenames(
            parent=self,
            title='Selecciona imágenes para procesar',
            filetypes=[
                ('Imágenes', '*.jpg *.jpeg *.png *.webp *.JPG *.JPEG *.PNG *.WEBP'),
                ('Todos los archivos', '*.*')
            ]
        )

        added=0
        rejected=[]

        for f in fs:
            try:
                p=Path(f)
                if not p.is_file():
                    continue

                # Validate using the actual file signature, not the extension.
                data=p.read_bytes()
                fmt=detect_format(data,p)

                if fmt not in ('jpeg','png','webp'):
                    rejected.append(p.name)
                    continue

                path_str=str(p.resolve())
                if path_str not in self.files:
                    self.files.append(path_str)
                    self.listbox.insert('end',path_str)
                    added += 1

            except Exception as e:
                rejected.append(f'{Path(f).name} ({e})')

        self.count.config(text=f'{len(self.files)} archivos')

        if added:
            self.status.config(text=f'{added} imagen(es) agregada(s).')
        elif fs and rejected:
            self.status.config(text='No se pudo reconocer el formato de la imagen seleccionada.')
            messagebox.showwarning(
                'MetaDataCleaner',
                'No se agregaron las imágenes seleccionadas porque su formato no es compatible.\\n\\n'
                'Formatos compatibles: JPG/JPEG, PNG y WebP.'
            )

    def clear(self):
        self.files.clear()
        self.listbox.delete(0,'end')
        self.count.config(text='0 archivos')
        self.status.config(text='Listo.')

    def clean(self):
        if not self.files:
            messagebox.showinfo('MetaDataCleaner','Agrega al menos una imagen.')
            return
        ok=0
        errors=[]
        self.progress['maximum']=len(self.files)
        self.progress['value']=0

        for idx,f in enumerate(self.files,1):
            try:
                p=Path(f)
                out=normalized_reencode(p)
                ok += 1
                self.status.config(text=f'Listo: {p.name} → {out.name}')
                self.update_idletasks()
            except Exception as e:
                try:
                    size=Path(f).stat().st_size
                    head=Path(f).read_bytes()[:16].hex(' ')
                    errors.append(
                        f'{Path(f).name}: {e} | {size:,} bytes | firma: {head}'
                    )
                except Exception:
                    errors.append(f'{Path(f).name}: {e}')
            self.progress['value']=idx

        msg=f'Listo. {ok} de {len(self.files)} archivos procesados.\n\n'
        msg+='Las copias terminan en la misma carpeta con _CLEAN.'
        if errors:
            msg+='\n\nErrores:\n'+'\n'.join(errors[:8])
        messagebox.showinfo('MetaDataCleaner',msg)

if __name__=='__main__':
    App().mainloop()
