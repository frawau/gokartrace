import datetime as dt
import pycountry
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.colors import black, darkred, white
# from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab_qrcode import QRCodeImage
from reportlab.graphics import renderPDF
from reportlab.lib.utils import ImageReader
from django.db.models import Q#
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.conf import settings
from pathlib import Path
from io import BytesIO
from pathlib import Path

from .models import Round, Person, team_member

FLAGDIR = Path("/home/pi/gokartrace/static/flags")


class GenerateCardPDF(View):
    def get(self, request, pk):
        end_date = dt.date.today()
        start_date = end_date - dt.timedelta(days=3)
        round = Round.objects.filter(
            Q(start__date__range=[start_date, end_date]) & Q(started__isnull=True)
        ).first()
        person = get_object_or_404(Person, pk=pk)
        filename = f"card_{person.nickname}.pdf"
        tm = team_member.objects.get(member=person, team__round=round)
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        p = canvas.Canvas(response, pagesize=A5)
        width, height = A5

        def contentFit(image_data, max_width, max_height):
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

        def draw_namecard(canvas, teammember):
            card_width = 91 * mm
            card_height = 55 * mm
            canvas.rect(0, 0, card_width, card_height)
            person = teammember.member
            canvas.setFont("Helvetica-Bold", 22)
            nickname = person.nickname if person.nickname else "Silly"
            text_width = canvas.stringWidth(nickname, "Helvetica-Bold", 22)
            x_nickname = (card_width - text_width) / 2
            canvas.drawString(x_nickname, card_height - 20 * mm, nickname)

            canvas.setFont("Helvetica", 14)
            full_name = f"{person.firstname} {person.surname}"
            text_width = canvas.stringWidth(full_name, "Helvetica", 14)
            x_fullname = (card_width - text_width) / 2
            canvas.drawString(x_fullname, card_height - 28 * mm, full_name)

            if person.mugshot:
                try:
                    img_data = person.mugshot.read()
                    img_width, img_height, img = contentFit(
                        img_data, 33.5 * mm, 43.5 * mm
                    )
                    if img:
                        x_img = 2 * mm
                        y_img = 3 * mm
                        canvas.drawImage(img, x_img, y_img, img_width, img_height)
                except Exception as e:
                    print(f"Error loading mugshot: {e}")

            qr_data = f"Name: {person.nickname} ({full_name})\nID: {teammember.pk}"
            qr_code = QRCodeImage(qr_data, 10 * mm)
            # qr_code = QrCodeWidget(qr_data)
            # qr_code.barHeight = 10 * mm
            # qr_code.barWidth = 10 * mm
            qr_code.drawOn(canvas, card_width - 25 * mm, 5 * mm)

            canvas.setFont("Helvetica-Bold", 8)
            id_text = f"{person.pk:04d}"
            text_width_id = canvas.stringWidth(id_text, "Helvetica-Bold", 8)
            x_id = (
                # card_width - 25 * mm - (qr_code.barWidth * 5) - 2 * mm - text_width_id
                card_width - 25 * mm - (qr_code.width * 5) - 2 * mm - text_width_id
            )
            canvas.drawString(x_id, 10 * mm, id_text)

            canvas.setFont("Helvetica", 10)
            nationality_name = "N/A"
            try:
                country = pycountry.countries.get(alpha_2=person.country.code)
                if country:
                    nationality_name = country.name
                    flagf = FLAGDIR / "{country.alpha2.lower()}.png"
                    if not flagf.exists():
                        flagf = FLAGDIR / "un.png"

                        flag_image_data = flagf.read_bytes()
                        flag_width = 15 * mm
                        flag_height = 10 * mm
                        img_width, img_height, flag_img = contentFit(
                            flag_image_data, flag_width, flag_height
                        )
                        if flag_img:
                            canvas.drawImage(
                                flag_img, 5 * mm, 15 * mm, img_width, img_height
                            )

            except AttributeError:
                pass  # Handle cases where country code might be invalid or not set

            text_width_nat = canvas.stringWidth(nationality_name, "Helvetica", 10)
            x_nat = 20 * mm
            canvas.drawString(x_nat, 15 * mm, nationality_name)

        def draw_doublenamecard(canvas, teammember):
            card_width = 91 * mm
            card_height = 130 * mm
            canvas.rect(0, 0, card_width, card_height)  # Optional: Draw border

            person = teammember.member
            # Nickname
            canvas.setFont("Helvetica-Bold", 22)
            nickname = person.nickname if person.nickname else "N/A"
            text_width = canvas.stringWidth(nickname, "Helvetica-Bold", 22)
            x_nickname = (card_width - text_width) / 2
            canvas.drawString(x_nickname, card_height - 20 * mm, nickname)

            # Full Name
            canvas.setFont("Helvetica", 16)
            full_name = f"{person.firstname} {person.surname}"
            text_width = canvas.stringWidth(full_name, "Helvetica", 16)
            x_fullname = (card_width - text_width) / 2
            canvas.drawString(x_fullname, card_height - 30 * mm, full_name)

            # --- Mugshot ---
            if person.mugshot:
                try:
                    img_data = person.mugshot.read()
                    img_width, img_height, img = contentFit(img_data, 35 * mm, 35 * mm)
                    if img:
                        x_img = (card_width - img_width) / 2
                        y_img = card_height - 50 * mm - img_height
                        canvas.drawImage(img, x_img, y_img, img_width, img_height)
                except Exception as e:
                    print(f"Error loading mugshot: {e}")

            # --- QR Code ---
            qr_data = f"Name: {person.nickname} ({full_name})\nID: {teammember.pk}"
            qr_code = QRCodeImage(qr_data, 12 * mm)
            # qr_code = QrCodeWidget(qr_data)
            # qr_code.barHeight = 12 * mm
            # qr_code.barWidth = 12 * mm
            qr_code.drawOn(canvas, card_width - 30 * mm, 10 * mm)

            # --- ID Number ---
            canvas.setFont("Helvetica-Bold", 8)
            id_text = f"{person.pk:04d}"
            text_width_id = canvas.stringWidth(id_text, "Helvetica-Bold", 8)
            x_id = (
                # card_width - 30 * mm - (qr_code.barWidth * 5) - 2 * mm - text_width_id
                card_width - 30 * mm - (qr_code.width * 5) - 2 * mm - text_width_id
            )
            canvas.drawString(x_id, 15 * mm, id_text)

            # --- Nationality (Country) ---
            canvas.setFont("Helvetica", 12)
            nationality_name = "N/A"
            try:
                country = pycountry.countries.get(alpha_2=person.country.code)
                if country:
                    nationality_name = country.name
                    flagf = FLAGDIR / "{country.alpha2.lower()}.png"
                    if not flagf.exists():
                        flagf = FLAGDIR / "un.png"

                        flag_image_data = flagf.read_bytes()
                        flag_width = 15 * mm
                        flag_height = 10 * mm
                        img_width, img_height, flag_img = contentFit(
                            flag_image_data, flag_width, flag_height
                        )
                        if flag_img:
                            canvas.drawImage(
                                flag_img, 5 * mm, 15 * mm, img_width, img_height
                            )

            except AttributeError:
                pass

            canvas.drawString(20 * mm, 40 * mm, nationality_name)

        card_type = request.GET.get("card_type", "name")

        if card_type == "double":
            draw_doublenamecard(p, tm)
        else:
            draw_namecard(p, tm)

        p.save()
        return response
