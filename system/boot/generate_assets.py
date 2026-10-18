#!/usr/bin/env python3
"""Original blue CRT artwork. Runtime installation needs no image libraries."""
import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops, ImageFont

BASE=Path(__file__).resolve().parent
FONT=Path('/usr/share/fonts/truetype/dejavu')
BLUE=(4,4,126)
WHITE=(226,243,255)
CYAN=(137,213,255)

def background(frame=True):
    image=Image.new('RGB',(1920,1080),(10,10,171))
    shade=Image.radial_gradient('L').resize(image.size).point(lambda v:int(v*.55))
    image=Image.composite(Image.new('RGB',image.size,(0,0,22)),image,shade)
    layer=Image.new('RGBA',image.size);draw=ImageDraw.Draw(layer)
    for y in range(0,1080,3):draw.line((0,y,1920,y),fill=(0,0,20,55))
    for x in range(0,1920,3):draw.line((x,0,x,1080),fill=(80,130,255,10))
    # Glass reflections follow the screen edge; the centre stays readable.
    for inset in range(4,22,2):
        alpha=int(34*(1-(inset-4)/18))
        draw.rounded_rectangle((inset,inset,1919-inset,1079-inset),radius=30,outline=(130,165,255,alpha),width=2)
    for y in range(24,150):
        alpha=int(10*(1-(y-24)/126))
        draw.line((40,y,1880,y),fill=(180,200,255,alpha))
    return Image.alpha_composite(image.convert('RGBA'),layer).convert('RGB')

def bevel(draw,box,fill=(174,174,174,255)):
    x,y,r,b=box
    draw.rectangle((x+9,y+9,r+9,b+9),fill=(0,0,22,235))
    draw.rectangle(box,fill=fill)
    draw.line((x+3,b-3,x+3,y+3,r-3,y+3),fill=(246,246,240),width=2)
    draw.line((r-3,y+3,r-3,b-3,x+3,b-3),fill=(44,44,48),width=2)
    draw.rectangle((x+8,y+8,r-8,b-8),outline=(107,107,112),width=1)

def computer(size=112,phase=0):
    # Pixel geometry, intentionally sharp: no modern vector smoothing.
    image=Image.new('RGBA',(112,112));draw=ImageDraw.Draw(image)
    draw.rectangle((12,12,99,76),fill=(16,43,172),outline=WHITE,width=3)
    draw.rectangle((19,19,92,66),fill=(0,0,80),outline=(75,132,239),width=2)
    for y in range(21,65,4):draw.line((21,y,90,y),fill=(13,26,102,255))
    y=22+int(phase*42)%42
    draw.line((21,y,90,y),fill=(70,147,232,185),width=2)
    draw.rectangle((48,77,63,85),fill=WHITE)
    draw.polygon([(40,85),(71,85),(80,94),(31,94)],fill=WHITE)
    draw.rectangle((13,99,98,102),fill=(126,181,253))
    if int(phase*4)%2==0:draw.rectangle((28,48,39,51),fill=CYAN)
    return image.resize((size,size),Image.Resampling.NEAREST)

def loading(index):
    image=Image.new('RGBA',(640,300));draw=ImageDraw.Draw(image)
    bevel(draw,(12,24,616,263))
    font=ImageFont.truetype(str(FONT/'DejaVuSansMono.ttf'),19)
    small=ImageFont.truetype(str(FONT/'DejaVuSansMono.ttf'),14)
    draw.rectangle((234,24,395,39),fill=(174,174,174))
    draw.text((315,32),' SYSTEM ',font=font,anchor='mm',fill=(10,10,170))
    draw.text((315,91),'Iniciando Linux',font=font,anchor='mm',fill=(12,12,20))
    draw.text((315,122),'Espere un momento'+'.'*(1+index//24),font=small,anchor='mm',fill=(55,55,65))
    draw.rectangle((60,160,566,191),fill=(2,2,97),outline=(75,75,80),width=2)
    draw.line((60,192,567,192,567,161),fill=(241,241,235),width=2)
    position=(index/72)*590-40
    for offset in range(0,112,22):
        left=64+int(position)-offset
        if 64<=left<=541:
            draw.rectangle((left,164,left+18,187),fill=(125,156,224))
            draw.line((left,164,left+18,164),fill=(224,238,255))
    draw.text((315,231),'[  Espere  ]',font=small,anchor='mm',fill=(70,70,80))
    # Phosphor mask is baked into the panel as well as the wallpaper.
    for y in range(24,264,3):
        for x in range(13,616):
            r,g,b,a=image.getpixel((x,y));image.putpixel((x,y),(int(r*.94),int(g*.94),int(b*.94),a))
    return image

def power_frame(index,mode):
    image=Image.new('RGBA',(640,300));d=ImageDraw.Draw(image)
    bevel(d,(12,24,616,263))
    font=ImageFont.truetype(str(FONT/'DejaVuSansMono.ttf'),19)
    small=ImageFont.truetype(str(FONT/'DejaVuSansMono.ttf'),14)
    d.rectangle((234,24,395,39),fill=(174,174,174))
    d.text((315,32),' POWER ',font=font,anchor='mm',fill=(10,10,170))
    pulse=.5+.5*math.sin(index/48*math.pi*2)
    amber=(int(162+60*pulse),int(93+55*pulse),22)
    d.arc((287,58,343,114),-50,230,fill=(48,48,57),width=8)
    d.arc((289,60,341,112),-50,230,fill=amber,width=4)
    d.line((315,53,315,85),fill=amber,width=5)
    d.text((315,147),'Reiniciando equipo' if mode=='reboot' else 'Apagando equipo',font=font,anchor='mm',fill=(12,12,20))
    d.text((315,180),'Cerrando servicios'+'.'*(1+index//16),font=small,anchor='mm',fill=(55,55,65))
    for j in range(9):
        x=254+j*14
        value=int(80+105*(.5+.5*math.sin(index/48*math.pi*2+j*.7)))
        d.rectangle((x,222,x+8,226),fill=(value,value,int(value*.8)))
    return image

def grub_details(grub):
    icons=grub/'icons';icons.mkdir(exist_ok=True)
    for name in ('gnu-linux','parrot','debian','ubuntu','linux','windows','os','unknown','recovery','submenu','settings','efi'):
        im=Image.new('RGBA',(32,32));d=ImageDraw.Draw(im)
        if name in ('settings','efi'):
            for j in range(5):
                d.rectangle((2,5+j*5,29,6+j*5),fill=(210,210,198))
                d.rectangle((5+j*5,2,6+j*5,29),fill=(210,210,198))
            d.rectangle((7,7,24,24),fill=(31,48,48),outline=(234,234,214))
            d.rectangle((11,11,20,20),fill=(95,116,102),outline=(4,18,18))
        elif name in ('submenu','recovery'):
            d.polygon([(3,7),(13,7),(16,11),(29,11),(29,26),(3,26)],fill=(211,181,87),outline=(54,42,16))
            d.rectangle((5,14,27,24),fill=(244,219,133));d.line((4,12,28,12),fill=(255,245,178))
        else:
            d.rectangle((4,4,27,27),fill=(165,167,165),outline=(23,23,30))
            d.line((5,26,5,5,26,5),fill=(246,245,226))
            d.rectangle((8,8,23,17),fill=(26,29,50),outline=(79,81,97))
            if name=='windows':
                for x,y,col in ((9,9,(222,83,58)),(17,9,(88,160,73)),(9,14,(81,147,211)),(17,14,(234,188,50))):d.rectangle((x,y,x+5,y+3),fill=col)
            else:d.line((10,13,13,15,20,10),fill=(159,206,248),width=2)
            d.rectangle((8,21,20,23),fill=(69,70,76));d.point((24,23),fill=(153,226,101))
        im.save(icons/(name+'.png'))
    # Three-part relief for the native timeout bar, plus classic keyboard caps.
    for style,bg in (('timer',(17,17,59)),('timer-fill',(118,145,216))):
        for name in ('nw','n','ne','w','c','e','sw','s','se'):
            im=Image.new('RGB',(3,3),bg);d=ImageDraw.Draw(im)
            if 'n' in name:d.line((0,0,2,0),fill=(233,238,245))
            if 's' in name:d.line((0,2,2,2),fill=(39,42,72))
            im.save(grub/(style+'_'+name+'.png'))
    for name,label,w in (('key-arrows','↑ ↓',76),('key-enter','ENTER',84),('key-escape','ESC',62)):
        im=Image.new('RGBA',(w,32));d=ImageDraw.Draw(im)
        bevel(d,(0,0,w-7,25),fill=(182,184,190))
        d.text(((w-7)/2,12),label,font=ImageFont.truetype(str(FONT/'DejaVuSansMono.ttf'),13),anchor='mm',fill=(19,20,32))
        im.save(grub/(name+'.png'))

def main():
    grub=BASE/'grub';ply=BASE/'plymouth';greeter=BASE/'greeter'
    grub_details(grub)
    (grub/'titlebar.png').unlink(missing_ok=True)
    subprocess.run(['gdk-pixbuf-thumbnailer','-s','144',str(grub/'computer.png'),str(grub/'computer-icon.png')],check=True)
    background().save(grub/'background.png',optimize=True)
    background(False).save(greeter/'background.png',optimize=True)
    background(False).save(ply/'background.png',optimize=True)
    Image.new('RGBA',(1,1)).save(greeter/'logo.png')
    cuts={'nw':(0,0,24,24),'n':(24,0,104,24),'ne':(104,0,128,24),
          'w':(0,24,24,104),'c':(24,24,104,104),'e':(104,24,128,104),
          'sw':(0,104,24,128),'s':(24,104,104,128),'se':(104,104,128,128)}
    tile=Image.new('RGBA',(128,128));d=ImageDraw.Draw(tile)
    bevel(d,(0,0,118,118))
    for name,box in cuts.items():tile.crop(box).save(grub/f'dialog_{name}.png')
    for name in cuts:
        tile=Image.new('RGBA',(2,2),(5,5,156,255))
        tile.save(grub/f'selection_{name}.png')
    # Small reusable overlays keep animation memory bounded on older laptops.
    import random
    rng=random.Random(1997)
    for index in range(16):
        noise=Image.new('RGBA',(480,270));d=ImageDraw.Draw(noise)
        for i in range(950):
            x=rng.randrange(480);y=rng.randrange(270)
            d.point((x,y),fill=(170,196,255,rng.randrange(12,40)))
        noise.save(ply/f'noise-{index}.png',optimize=True)
    band=Image.new('RGBA',(8,128));d=ImageDraw.Draw(band)
    for y in range(128):d.line((0,y,7,y),fill=(174,205,255,int(17*math.sin(math.pi*y/128)**2)))
    band.save(ply/'scan-band.png')
    Image.new('RGB',(8,8),'black').save(ply/'curtain.png')
    for mode in ('shutdown','reboot'):
        for index in range(48):power_frame(index,mode).save(ply/f'{mode}-{index}.png',optimize=True)
    frames=[]
    for i in range(72):
        frame=loading(i);frame.save(ply/f'frame-{i}.png',optimize=True)
        flattened=Image.new('RGBA',frame.size,BLUE+(255,));flattened.alpha_composite(frame)
        frames.append(flattened.convert('RGB'))
    frames[0].save(BASE/'preview.gif',save_all=True,append_images=frames[1:],duration=33,loop=0)
    for filename,size,fontname in [('mono-20',20,'DejaVuSansMono.ttf'),
                                   ('mono-16',16,'DejaVuSansMono.ttf'),('mono-bold-24',24,'DejaVuSansMono-Bold.ttf')]:
        subprocess.run(['grub-mkfont','-s',str(size),'-o',str(grub/(filename+'.pf2')),str(FONT/fontname)],check=True)
    for name in ('sans-16.pf2','sans-22.pf2'):
        (grub/name).unlink(missing_ok=True)

if __name__=='__main__':main()
