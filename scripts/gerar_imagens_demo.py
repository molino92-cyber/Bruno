"""Cria ilustrações originais para a vitrine de demonstração, sem fotos externas."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent / "assets" / "demo"
ROOT.mkdir(parents=True, exist_ok=True)
COLORS = ["#e49b91", "#734638", "#d7ac75", "#e8c2a0"]


def cake(d, x=300, y=285, color="#e49b91", scale=1):
    def box(a, b, c, e):
        return (x+a*scale, y+b*scale, x+c*scale, y+e*scale)
    d.ellipse(box(-175, 50, 175, 100), fill="#d8c7b8")
    d.ellipse(box(-165, 40, 165, 85), fill="#fffdf9")
    d.rounded_rectangle(box(-130, -95, 130, 52), radius=int(20*scale), fill=color)
    d.ellipse(box(-130, 17, 130, 72), fill=color)
    d.ellipse(box(-130, -122, 130, -66), fill="#fff1db")
    for pos in range(-110, 120, 26):
        d.ellipse(box(pos-10, -100, pos+10, -60), fill="#fff1db")
    for pos in [-80, -40, 0, 40, 80]:
        d.ellipse(box(pos-14, -115, pos+14, -91), fill="#f4d5ca")
        d.ellipse(box(pos-7, -119, pos+7, -105), fill="#b94d50")
    for pos in [-70, -25, 20, 65]:
        d.line(box(pos, -35, pos+10, -23), fill="#fff1db", width=3)


def sweet(d, x, y, kind="brigadeiro", color="#603e32"):
    d.ellipse((x-38, y+19, x+38, y+41), fill="#dbcbbd")
    if kind == "cupcake":
        d.polygon([(x-33,y),(x+33,y),(x+24,y+34),(x-24,y+34)], fill="#c48c65")
        for offset in [0, 15, 28]:
            d.ellipse((x-33+offset/2,y-31-offset,x+33-offset/2,y+10-offset),fill=color)
        d.ellipse((x-6,y-65,x+6,y-53),fill="#c55955")
    elif kind == "donut":
        d.ellipse((x-42,y-35,x+42,y+30),fill="#d6a06a")
        d.ellipse((x-38,y-34,x+38,y+22),fill=color)
        d.ellipse((x-12,y-16,x+12,y+6),fill="#f9f1e8")
    else:
        d.polygon([(x-37,y+5),(x+37,y+5),(x+28,y+34),(x-28,y+34)],fill="#d7b596")
        d.ellipse((x-29,y-36,x+29,y+17),fill=color)
        for dx,dy in [(-14,-15),(3,-22),(15,-6),(-3,0)]:
            d.line((x+dx,y+dy,x+dx+5,y+dy+5),fill="#e3bd8c",width=3)


for index, name in enumerate(["bolo-simples", "bolo-especial", "brigadeiros", "brigadeiros-especiais", "brigadeiros-personalizados", "cupcake", "donut", "topo", "kit1", "kit2", "kit3", "kit4"]):
    image = Image.new("RGB", (600, 420), "#faf4eb")
    d = ImageDraw.Draw(image)
    d.ellipse((390,-70,690,210),fill="#f1dfd2")
    d.ellipse((-120,235,110,470),fill="#eddbca")
    if name.startswith("bolo"):
        cake(d,color=COLORS[index % 4])
    elif name.startswith("kit"):
        cake(d,300,210,COLORS[index % 4],.72)
        for x in [150,250,350,450]:
            sweet(d,x,350,"cupcake" if x in [150,450] else "brigadeiro",COLORS[(index+1)%4])
    elif name == "topo":
        cake(d,300,315,"#e4c5a8",.65)
        d.line((300,240,300,140),fill="#ba916b",width=5)
        d.rounded_rectangle((190,80,410,170),radius=25,fill="#d86b52")
        d.text((258,116),"PARABENS",fill="white")
        for x,y in [(210,75),(402,70),(420,170),(180,155)]:
            d.regular_polygon((x,y,13),5,fill="#d3a354")
    else:
        kind = name if name in ["cupcake","donut"] else "brigadeiro"
        for row in range(2):
            for col in range(3):
                sweet(d,170+col*130,175+row*125,kind,COLORS[(index+col)%4] if "personalizados" in name else COLORS[index%4])
    d.text((22,392),"DOCE ATELIE  /  ILUSTRACAO DE EXEMPLO",fill="#9c7d67")
    image.save(ROOT / f"{name}.png",optimize=True)

for index, name in enumerate(["Ana", "Beatriz", "Camila", "Daniela", "Elisa", "Fernanda"]):
    image = Image.new("RGB", (160,160), ["#edd4c5","#dddce7","#c8ddd6"][index%3])
    d = ImageDraw.Draw(image)
    d.ellipse((42,22,118,102),fill="#593f38")
    d.ellipse((48,34,112,106),fill=["#dfac88","#b47c59","#f1c8a4"][index%3])
    d.ellipse((25,100,135,215),fill=COLORS[index%4])
    d.arc((68,67,93,86),0,180,fill="#593f38",width=2)
    d.ellipse((64,59,68,64),fill="#593f38")
    d.ellipse((94,59,98,64),fill="#593f38")
    image.save(ROOT / f"cliente-{index}.png")
