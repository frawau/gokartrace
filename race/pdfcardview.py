import datetime as dt
import pycountry
from langdetect import detect, LangDetectException
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A6, A5, A4, A3
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
from io import BytesIO
from pathlib import Path

from .models import Round, Person, team_member

FLAGDIR = Path("/home/llama/gokartrace/static/flags")
LOGOIMG = Path("/home/llama/gokartrace/static/logos/gokartrace-logo.jpg")


class GenerateCardPDF(View):
    card_width = A5[0]
    card_height = A5[1]
    margin = 3 * mm

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

    def draw_drivercard(
        self, canvas, teammember, x, y, card_w, card_h, scaledmm=mm, rotate=True
    ):
        """This card is designed for A5, if printed on A4 ut needs to be rotated"""
        canvas.saveState()
        if rotate:
            canvas.rotate(90)
            canvas.translate(0, -self.card_height)
        canvas.translate(x, y)
        # canvas.rect(0, 0, card_w, card_h)  # Optional: Draw border

        person = teammember.member
        team = teammember.team

        # --- Team Name at the Top ---
        team_name = team.name if team.name else "Team Name"
        ftsz = self.textFit(team_name, canvas, card_w, 32, "Helvetica-Bold")
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
        sz = self.textFit(nickname, canvas, card_w - x_nick, 48, "Helvetica-Bold")
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
        y_full = y_nick - 5 - 42  # Adjust for spacing
        ftsz = self.textFit(full_name, canvas, card_w - x_full, 24, ufont)
        canvas.setFont(ufont, ftsz)
        canvas.drawString(x_full, y_full, full_name)

        # --- QR Code ---
        qr_data = f"Team: {team.name}\nMember: {person.nickname} ({full_name})\nID: {teammember.pk}"
        qr_size = card_h * 0.2
        qr_code = QRCodeImage(qr_data, qr_size)
        qr_x = 15 * scaledmm
        qr_y = 15 * scaledmm
        if teammember.driver:
            qr_code.drawOn(canvas, qr_x, qr_y)

        # --- Flag and Weight ---
        flag_width = 30 * scaledmm
        flag_height = 20 * scaledmm

        nationality_name = "N/A"
        try:
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
                        canvas.drawImage(
                            flag_img, flag_x, flag_y, img_width, img_height
                        )
        except AttributeError as e:
            print(f"Fils de p...: {e}")
            pass

            # --- Weight ---
            if teammember.driver:
                canvas.setFont("Helvetica-Bold", 48)
                weight_text = f"{teammember.weight:.1f} kg"
                text_width_weight = canvas.stringWidth(
                    weight_text, "Helvetica-Bold", 48
                )
                weight_x = qr_x + qr_size + 25 * scaledmm
                weight_y = qr_y + qr_size - 5 - 60  # Adjust for spacing
                canvas.drawString(weight_x, weight_y, weight_text)

            if teammember.manager:
                canvas.setFont("Helvetica-Bold", 32)
                canvas.setFillColor(darkred)
                manager_text = "Manager"
                text_width_manager = canvas.stringWidth(
                    manager_text, "Helvetica-Bold", 32
                )
                manager_x = qr_x + qr_size + 25 * scaledmm
                manager_y = qr_y + qr_size - 5 - 60 - 60  # Adjust for spacing
                canvas.drawString(manager_x, manager_y, manager_text)

            canvas.restoreState()

    def get(self, request, pk):

        end_date = dt.date.today()
        start_date = end_date - dt.timedelta(days=3)
        cround = Round.objects.filter(
            Q(start__date__range=[start_date, end_date]) & Q(started__isnull=True)
        ).first()

        filename = f"card_{round(dt.datetime.now().timestamp())}.pdf"
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        # Create a PDF in memory
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)  # Use A4 for 2 cards
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
        scaledmm = 0.5 * mm
        self.margin = 3 * scaledmm
        self.card_width = A6[0]
        self.card_height = A6[1]
        cards_per_row = 2
        cards_per_col = 2
        card_spacing_x = 0 * scaledmm
        card_spacing_y = 0 * scaledmm

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
            x_offset = self.card_width * curcol + self.margin
            y_offset = self.card_height * currow + self.margin

            # Draw the first card
            self.draw_drivercard(
                p,
                tm,
                x_offset,
                y_offset,
                self.card_width - 2 * self.margin,
                self.card_height - 2 * self.margin,
                scaledmm,
                False,
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
