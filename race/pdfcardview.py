import datetime as dt
import pycountry
import json
from langdetect import detect, LangDetectException
from reportlab.pdfgen import canvas
import reportlab.lib.pagesizes as pagesz
from reportlab.lib.units import mm
from reportlab.lib.colors import black, darkred, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab_qrcode import QRCodeImage
from reportlab.lib.utils import ImageReader
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.conf import settings
from pathlib import Path
from cryptography.fernet import Fernet
from base64 import b64encode
from io import BytesIO
from pathlib import Path

from .models import Round, Person, team_member, Config

FLAGDIR = Path("/home/llama/gokartrace/static/flags")
LOGOIMG = Path("/home/llama/gokartrace/static/logos/gokartrace-logo.jpg")


class GenerateCardPDF(View):
    card_width = pagesz.A5[0]
    card_height = pagesz.A5[1]
    rotate = True

    def contentFit(self, image_data, max_width, max_height):
        try:
            img = ImageReader(BytesIO(image_data))
            img_width, img_height = img.getSize()
            img_ratio = img_width / img_height
            max_ratio = max_width / max_height

            if img_ratio > max_ratio:
                new_width = max_width
                new_height = max_width / img_ratio
            else:
                new_height = max_height
                new_width = max_height * img_ratio
            return new_width, new_height, img
        except ImportError:
            print("Warning: Pillow/PIL not found, cannot fit images.")
            return 0, 0, None

    def textFit(self, text, canvas, max_width, fontsize, font):
        while fontsize > 0:
            # canvas.setFont(font, fontsize)
            text_width = canvas.stringWidth(text, "Helvetica-Bold", fontsize)
            if text_width <= max_width:
                return fontsize
            fontsize -= 1
        return fontsize

    def draw_drivercard(self, canvas, teammember, x, y):
        """This card is designed for A5, with a 3mm margin. Let's scale things"""
        scalefactor = self.card_width / pagesz.A5[0]
        scaledmm = mm * scalefactor
        margin = 3 * scaledmm
        canvas.saveState()
        canvas.translate(x, y)
        if self.rotate:
            canvas.rotate(90)
            canvas.translate(0, -self.card_height)
        canvas.translate(margin, margin)
        card_w = self.card_width - 2 * margin
        card_h = self.card_height - 2 * margin
        # canvas.rect(0, 0, card_w, card_h)  # Optional: Draw border

        person = teammember.member
        team = teammember.team

        # --- Team Name at the Top ---
        team_name = team.name if team.name else "Team Name"
        ftsz = self.textFit(
            team_name, canvas, card_w, int(32 * scalefactor + 0.5), "Helvetica-Bold"
        )
        text_width_team = canvas.stringWidth(team_name, "Helvetica-Bold", ftsz)
        x_team = (card_w - text_width_team) / 2
        canvas.setFont("Helvetica-Bold", ftsz)
        canvas.drawString(x_team, card_h - 10 * scaledmm, team_name)

        # --- Logo  ---
        logo_width = 35 * scaledmm
        logo_height = 20 * scaledmm
        logo_x = logo_width / 2
        logo_y = card_h - logo_height - 10 * scaledmm

        try:
            img_data = LOGOIMG.read_bytes()
            img_width, img_height, img = self.contentFit(
                img_data, logo_width, logo_height
            )
            if img:
                canvas.drawImage(img, logo_x, logo_y, img_width, img_height)
        except Exception as e:
            print(f"Error loading mugshot: {e}")
        # --- Team Number (Left) ---
        canvas.setFont("Helvetica-Bold", 100)
        team_number_str = str(teammember.team.number) if teammember.team.number else "#"
        text_width_number = canvas.stringWidth(team_number_str, "Helvetica-Bold", 100)
        # x_number = 20 * scaledmm
        x_number = (self.card_width * 0.32 - text_width_number) / 2
        y_number = card_h * 0.7 - 10 * scaledmm
        canvas.drawString(x_number, y_number, team_number_str)

        # --- Mugshot (Right) ---
        mugshot_width = 35 * scaledmm
        mugshot_height = 45 * scaledmm
        mugshot_x = card_w - mugshot_width - 30 * scaledmm
        mugshot_y = card_h - 30 * scaledmm - mugshot_height

        if person.mugshot:
            try:
                img_data = person.mugshot.read()
                img_width, img_height, img = self.contentFit(
                    img_data, mugshot_width, mugshot_height
                )
                if img:
                    canvas.drawImage(img, mugshot_x, mugshot_y, img_width, img_height)
            except Exception as e:
                print(f"Error loading mugshot: {e}")

        # --- Nickname ---  Centered
        x_nick = mugshot_x - 20 * scaledmm
        y_nick = mugshot_y - 30 * scaledmm  # Adjust for spacing
        nickname = person.nickname if person.nickname else "N/A"
        sz = self.textFit(
            nickname,
            canvas,
            card_w - x_nick,
            int(48 * scalefactor + 0.5),
            "Helvetica-Bold",
        )
        canvas.setFont("Helvetica-Bold", sz)
        canvas.drawString(x_nick, y_nick, nickname)

        # --- Full Name --- Centered
        full_name = f"{person.firstname} {person.surname}"
        try:
            lang = detect(full_name)
        except LangDetectException:
            lang = "unknown"

        if lang == "th":
            ufont = "THFont"
        elif lang == "jp":
            ufont = "JPFont"
        elif lang == "kr":
            ufont = "KRFont"
        elif lang == "zh":
            ufont = "ZHFont"
        else:
            ufont = "ENFont"

        x_full = mugshot_x - 20 * scaledmm
        y_full = y_nick - 47 * scalefactor  # Adjust for spacing
        ftsz = self.textFit(
            full_name, canvas, card_w - x_full, int(24 * scalefactor + 0.5), ufont
        )
        canvas.setFont(ufont, ftsz)
        canvas.drawString(x_full, y_full, full_name)

        # --- QR Code ---
        docrypt = Fernet(teammember.team.round.qr_fernet)
        qr_data = json.dumps(
            {
                "info": f"{person.nickname}\n{team.name}",
                "data": b64encode(docrypt(str(teammember.pk).encode())).decode("ascii"),
            }
        )
        qr_size = card_h * 0.2
        qr_code = QRCodeImage(qr_data, qr_size)
        qr_x = 15 * scaledmm
        qr_y = 15 * scaledmm
        if teammember.driver:
            qr_code.drawOn(canvas, qr_x, qr_y)

        # --- Flag and Weight ---
        flag_width = 37 * scaledmm
        flag_height = 25 * scaledmm

        try:
            nationality_name = "World Citizen"
            flagf = FLAGDIR / "un.png"
            if person.country:
                country = pycountry.countries.get(alpha_2=person.country.code)
                if country:
                    nationality_name = country.name
                    flagf = FLAGDIR / f"{country.alpha_2.lower()}.png"
                    if not flagf.exists():
                        flagf = FLAGDIR / "un.png"

            flag_image_data = flagf.read_bytes()
            img_width, img_height, flag_img = self.contentFit(
                flag_image_data, flag_width, flag_height
            )
            flag_x = (self.card_width * 0.32 - img_width) / 2
            flag_y = card_h * 0.4
            if flag_img:
                canvas.drawImage(flag_img, flag_x, flag_y, img_width, img_height)
            nat_y = flag_y - 10 * scaledmm
            canvas.setFont("Helvetica", int(18 * scalefactor + 0.5))
            canvas.drawString(flag_x, nat_y, nationality_name)
        except AttributeError as e:
            print(f"Fils de p...: {e}")
            pass

        # --- Weight ---
        if teammember.driver:
            canvas.setFont("Helvetica-Bold", int(48 * scalefactor + 0.5))
            weight_text = f"{teammember.weight:.1f} kg"
            text_width_weight = canvas.stringWidth(
                weight_text, "Helvetica-Bold", int(48 * scalefactor + 0.5)
            )
            weight_x = qr_x + qr_size + 25 * scaledmm
            weight_y = qr_y + qr_size  # Adjust for spacing
            canvas.drawString(weight_x, weight_y, weight_text)

        if teammember.manager:
            canvas.setFont("Helvetica-Bold", int(32 * scalefactor + 0.5))
            canvas.setFillColor(darkred)
            manager_text = "Manager"
            text_width_manager = canvas.stringWidth(
                manager_text, "Helvetica-Bold", int(32 * scalefactor + 0.5)
            )
            manager_x = qr_x + qr_size + 25 * scaledmm
            manager_y = qr_y + qr_size - 65 * scalefactor  # Adjust for spacing
            canvas.drawString(manager_x, manager_y, manager_text)
        maxtw, maxt = teammember.team.round.driver_time_limit(teammember)
        if maxtw:
            maxt_x = qr_x + qr_size + 25 * scaledmm
            maxt_y = qr_y + qr_size - 125 * scalefactor  #
            (
                tl_text
                + f"{maxtw.title()} driving limit: {(dt.datetime(2025,4,1) + maxt).strftime('%H:%M:%S')}"
            )
            canvas.setFont("Helvetica", int(18 * scalefactor + 0.5))
            canvas.drawString(flag_x, nat_y, tl_text)

        canvas.restoreState()

    def ready_canvas(self):
        sizelist = {
            "A0": pagesz.A0,
            "A1": pagesz.A1,
            "A2": pagesz.A2,
            "A3": pagesz.A3,
            "A4": pagesz.A4,
            "A5": pagesz.A5,
            "A6": pagesz.A6,
        }
        try:
            pagea = Config.objects.filter(name="page size").first().value
        except:
            pagea = "A4"
        try:
            carda = Config.objects.filter(name="card size").first().value
        except:
            carda = "A6"
        pageanum = int(pagea.strip()[1])
        cardanum = int(carda.strip()[1])
        if pageanum > cardanum:
            raise Exception("Wrong configuration. The card won't fit on the page.")

        self.card_width = sizelist[carda][0]
        self.card_height = sizelist[carda][1]
        # We expect bpth the card and page to follow ISO formats
        if (pageanum + cardanum) % 2:
            self.rotate = True
        else:
            self.rotate = False

        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=sizelist[pagea])  # Use A4 for 2 cards
        pdfmetrics.registerFont(
            TTFont("THFont", "/usr/local/share/fonts/NotoSansThai-Regular.ttf")
        )
        pdfmetrics.registerFont(
            TTFont("JPFont", "/usr/local/share/fonts/NotoSansJP-Regular.ttf")
        )
        pdfmetrics.registerFont(
            TTFont("KRFont", "/usr/local/share/fonts/NotoSansKR-Regular.ttf")
        )
        pdfmetrics.registerFont(
            TTFont("ZHFont", "/usr/local/share/fonts/NotoSansTC-Regular.ttf")
        )
        pdfmetrics.registerFont(
            TTFont("ENFont", "/usr/local/share/fonts/NotoSans-Regular.ttf")
        )
        return p, buffer

    def get(self, request, pk):

        end_date = dt.date.today()
        start_date = end_date - dt.timedelta(days=3)
        cround = Round.objects.filter(
            Q(start__date__range=[start_date, end_date]) & Q(started__isnull=True)
        ).first()
        if cround is None:
            return render(request, "pages/norace.html")

        filename = f"card_{round(dt.datetime.now().timestamp())}.pdf"
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        # Create a PDF in memory
        p, buffer = self.ready_canvas()
        pagesize = p._pagesize
        if self.rotate:
            cards_per_row = int(pagesize[1] / self.card_width)
            cards_per_col = int(pagesize[0] / self.card_height)
        else:
            cards_per_row = int(pagesize[1] / self.card_height)
            cards_per_col = int(pagesize[0] / self.card_width)

        longpk = pk
        currow = 0
        curcol = 0

        while longpk % 10000:
            cpk = longpk % 10000
            longpk = longpk // 10000
            try:
                person = get_object_or_404(Person, pk=cpk)
                tm = team_member.objects.get(member=person, team__round=cround)
            except:
                print("Error: Person not found in a current team.")
                continue
            # Calculate the position for the card on the A4 sheet
            if self.rotate:
                x_offset = self.card_height * curcol
                y_offset = self.card_width * currow
            else:
                x_offset = self.card_width * curcol
                y_offset = self.card_height * currow

            # Draw the card
            self.draw_drivercard(
                p,
                tm,
                x_offset,
                y_offset,
            )
            curcol = (curcol + 1) % cards_per_col
            if curcol == 0:
                currow = (currow + 1) % cards_per_row
                if currow == 0:
                    p.showPage()

        p.save()

        # Get the PDF content from the buffer
        pdf_content = buffer.getvalue()
        buffer.close()

        response.write(pdf_content)
        return response
