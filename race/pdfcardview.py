import datetime as dt
import pycountry
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A5, A4
from reportlab.lib.units import mm
from reportlab.lib.colors import black, darkred, white
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

class GenerateCardPDF(View):
    def get(self, request, pk):

        if pk >= 10000:
            pk1 = pk // 10000
            pk2 = pk % 10000
        else:
            pk1 = pk
            pk2 = None
        end_date = dt.date.today()
        start_date = end_date - dt.timedelta(days=3)
        cround = Round.objects.filter(
            Q(start__date__range=[start_date, end_date]) & Q(started__isnull=True)
        ).first()

        person = get_object_or_404(Person, pk=pk1)
        if pk2:
            person2 = get_object_or_404(Person, pk=pk2)
        filename = f"card_{person.nickname}.pdf"
        try:
            tm = team_member.objects.get(member=person, team__round=cround)
            if pk2:
                tm2 = team_member.objects.get(member=person2, team__round=cround)
            else:
                tm2 = None
        except team_member.DoesNotExist:
            return HttpResponse("Error: Person not found in a current team.", status=404)

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        # Create a PDF in memory
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)  # Use A4 for 2 cards

        margin = 3 * mm
        card_width = A5[0] - 2 * margin
        card_height = A5[1] - 2 * margin
        cards_per_row = 2
        card_spacing_x = 0 * mm
        card_spacing_y = 0 * mm

        # Calculate the position for the first card on the A4 sheet
        x_offset = margin
        y_offset = margin

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

        def textFit(text, canvas, max_width, fontsize, font):
            while fontsize > 0:
                # canvas.setFont(font, fontsize)
                text_width = canvas.stringWidth(text, "Helvetica-Bold", fontsize)
                if text_width <= max_width:
                    return fontsize
                fontsize -= 1
            return fontsize

        def draw_drivercard(canvas, teammember, x, y, card_w, card_h):
            canvas.saveState()
            canvas.rotate(90)
            canvas.translate(0, -card_height)
            canvas.translate(x,y)
            # canvas.rect(0, 0, card_w, card_h)  # Optional: Draw border

            person = teammember.member
            team = teammember.team

            # --- Team Name at the Top ---
            canvas.setFont("Helvetica-Bold", 18)
            team_name = team.name if team.name else "Team Name"
            text_width_team = canvas.stringWidth(team_name, "Helvetica-Bold", 18)
            x_team = (card_w - text_width_team) / 2
            canvas.drawString(x_team, card_h - 10 * mm, team_name)

            # --- Team Number (Left) ---
            canvas.setFont("Helvetica-Bold",100)
            team_number_str = str(teammember.team.number) if teammember.team.number else "#"
            text_width_number = canvas.stringWidth(team_number_str, "Helvetica-Bold", 100)
            # x_number = 20 * mm
            x_number = ((card_width + 2 * margin) * 0.32 - text_width_number) / 2
            y_number = card_h * 0.7 - 10 * mm
            canvas.drawString(x_number, y_number, team_number_str)

            # --- Mugshot (Right) ---
            mugshot_width = 35 * mm
            mugshot_height = 45 * mm
            mugshot_x = card_w - mugshot_width - 30 * mm
            mugshot_y = card_h - 30 * mm - mugshot_height

            if person.mugshot:
                try:
                    img_data = person.mugshot.read()
                    img_width, img_height, img = contentFit(img_data, mugshot_width, mugshot_height)
                    if img:
                        canvas.drawImage(img, mugshot_x, mugshot_y, img_width, img_height)
                except Exception as e:
                    print(f"Error loading mugshot: {e}")

            # --- Nickname ---  Centered
            x_nick = mugshot_x - 20 * mm
            y_nick = mugshot_y -30 * mm  # Adjust for spacing
            nickname = person.nickname if person.nickname else "N/A"
            sz = textFit(nickname,canvas,card_w-x_nick,48,"Helvetica-Bold")
            canvas.setFont("Helvetica-Bold", sz)
            canvas.drawString(x_nick, y_nick, nickname)

            # --- Full Name --- Centered
            canvas.setFont("Helvetica", 24)
            full_name = f"{person.firstname} {person.surname}"
            text_width_full = canvas.stringWidth(full_name, "Helvetica", 24)
            x_full =  mugshot_x - 20 * mm
            y_full = y_nick - 5 - 42 # Adjust for spacing
            canvas.drawString(x_full, y_full, full_name)

            # --- QR Code ---
            qr_data = f"Team: {team.name}\nMember: {person.nickname} ({full_name})\nID: {teammember.pk}"
            qr_size = card_h * 0.2
            qr_code = QRCodeImage(qr_data, qr_size)
            qr_x = 15 * mm
            qr_y = 15 * mm
            if teammember.driver:
                qr_code.drawOn(canvas, qr_x, qr_y)

            # --- Flag and Weight ---
            flag_width = 30 * mm
            flag_height = 20 * mm

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
                        img_width, img_height, flag_img = contentFit(flag_image_data, flag_width, flag_height)
                        flag_x = ((card_width + 2 * margin) * 0.32 - img_width) / 2
                        flag_y = card_h * 0.4
                        if flag_img:
                            canvas.drawImage(flag_img, flag_x, flag_y, img_width, img_height)
            except AttributeError as e:
                print(f"Fils de p...: {e}")
                pass

            # --- Weight ---
            if teammember.driver:
                canvas.setFont("Helvetica-Bold", 48)
                weight_text = f"{teammember.weight:.1f} kg"
                text_width_weight = canvas.stringWidth(weight_text, "Helvetica-Bold", 48)
                weight_x = qr_x + qr_size + 25 * mm
                weight_y = qr_y + qr_size - 5 - 60 # Adjust for spacing
                canvas.drawString(weight_x, weight_y, weight_text)

            if teammember.manager:
                canvas.setFont("Helvetica-Bold", 32)
                canvas.setFillColor(darkred)
                manager_text = "Manager"
                text_width_manager = canvas.stringWidth(manager_text, "Helvetica-Bold", 32)
                manager_x = qr_x + qr_size + 25 * mm
                manager_y = qr_y + qr_size - 5 - 60 - 60 # Adjust for spacing
                canvas.drawString(manager_x, manager_y, manager_text)


            canvas.restoreState()

        # Draw the first card
        draw_drivercard(p, tm, x_offset, y_offset, card_width - 2*margin, card_height-2*margin)

        # Draw the second card (if it fits)
        second_card_x = card_width + 3 * margin
        second_card_y = margin
        if second_card_y +  card_width <= A4[1]:
            if tm2:
                draw_drivercard(p, tm2, second_card_x, second_card_y, card_width - 2*margin, card_height - 2*margin)

        p.save()

        # Get the PDF content from the buffer
        pdf_content = buffer.getvalue()
        buffer.close()

        response.write(pdf_content)
        return response
