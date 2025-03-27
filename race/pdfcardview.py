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
        end_date = dt.date.today()
        start_date = end_date - dt.timedelta(days=3)
        round_obj = Round.objects.filter(
            Q(start__date__range=[start_date, end_date]) & Q(started__isnull=True)
        ).first()
        person = get_object_or_404(Person, pk=pk)
        filename = f"card_{person.nickname}.pdf"
        try:
            tm = team_member.objects.get(member=person, team__round=round_obj)
        except team_member.DoesNotExist:
            return HttpResponse("Error: Person not found in a current team.", status=404)

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        # Create a PDF in memory
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)  # Use A4 for 2 cards

        card_width = 91 * mm
        card_height = 130 * mm
        margin = 10 * mm
        cards_per_row = 2
        card_spacing_x = 10 * mm
        card_spacing_y = 10 * mm

        # Calculate the position for the first card on the A4 sheet
        x_offset = margin
        y_offset = A4[1] - margin - card_height

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

        def draw_drivercard(canvas, teammember, x, y, card_w, card_h):
            canvas.saveState()
            canvas.translate(x, y)
            canvas.rect(0, 0, card_w, card_h)  # Optional: Draw border

            person = teammember.member
            team = teammember.team

            # --- Team Name at the Top ---
            canvas.setFont("Helvetica-Bold", 18)
            team_name = team.name if team.name else "Team Name"
            text_width_team = canvas.stringWidth(team_name, "Helvetica-Bold", 18)
            x_team = (card_w - text_width_team) / 2
            canvas.drawString(x_team, card_h - 10 * mm, team_name)

            # --- Team Number (Left) ---
            canvas.setFont("Helvetica-Bold", 40)
            team_number_str = str(teammember.team.number) if teammember.team.number else "#"
            text_width_number = canvas.stringWidth(team_number_str, "Helvetica-Bold", 40)
            x_number = 10 * mm
            y_number = card_h * 0.7 - 20 * mm
            canvas.drawString(x_number, y_number, team_number_str)

            # --- Mugshot (Right) ---
            mugshot_width = card_w * 0.3
            mugshot_height = card_h * 0.3
            mugshot_x = card_w - mugshot_width - 10 * mm
            mugshot_y = card_h - 10 * mm - mugshot_height

            if person.mugshot:
                try:
                    img_data = person.mugshot.read()
                    img_width, img_height, img = contentFit(img_data, mugshot_width, mugshot_height)
                    if img:
                        canvas.drawImage(img, mugshot_x, mugshot_y, img_width, img_height)
                except Exception as e:
                    print(f"Error loading mugshot: {e}")

            # --- Nickname ---
            canvas.setFont("Helvetica-Bold", 16)
            nickname = person.nickname if person.nickname else "N/A"
            text_width_nick = canvas.stringWidth(nickname, "Helvetica-Bold", 16)
            x_nick = mugshot_x
            y_nick = mugshot_y - 10 * mm - 5 # Adjust for spacing
            canvas.drawString(x_nick, y_nick, nickname)

            # --- Full Name ---
            canvas.setFont("Helvetica", 12)
            full_name = f"{person.firstname} {person.surname}"
            text_width_full = canvas.stringWidth(full_name, "Helvetica", 12)
            x_full = mugshot_x
            y_full = y_nick - 5 - 12 # Adjust for spacing
            canvas.drawString(x_full, y_full, full_name)

            # --- QR Code ---
            qr_data = f"Team: {team.name}\nMember: {person.nickname} ({full_name})\nID: {teammember.pk}"
            qr_size = card_h * 0.2
            qr_code = QRCodeImage(qr_data, qr_size)
            qr_x = 10 * mm
            qr_y = 10 * mm
            qr_code.drawOn(canvas, qr_x, qr_y)

            # --- Flag and Weight ---
            flag_width = 15 * mm
            flag_height = 10 * mm
            flag_x = qr_x + qr_size + 5 * mm
            flag_y = qr_y + (qr_size - flag_height) / 2

            nationality_name = "N/A"
            try:
                if person.country:
                    country = pycountry.countries.get(alpha_2=person.country.code)
                    if country:
                        nationality_name = country.name
                        flagf = FLAGDIR / f"{country.alpha2.lower()}.png"
                        if not flagf.exists():
                            flagf = FLAGDIR / "un.png"

                        flag_image_data = flagf.read_bytes()
                        img_width, img_height, flag_img = contentFit(flag_image_data, flag_width, flag_height)
                        if flag_img:
                            canvas.drawImage(flag_img, flag_x, flag_y, img_width, img_height)
            except AttributeError:
                pass

            # --- Weight ---
            canvas.setFont("Helvetica", 10)
            weight_text = str(f"{team_member.weight:.1f} kg")
            text_width_weight = canvas.stringWidth(weight_text, "Helvetica", 10)
            weight_x = flag_x
            weight_y = flag_y - 5 - 10 # Adjust for spacing
            canvas.drawString(weight_x, weight_y, weight_text)

            canvas.restoreState()

        # Draw the first card
        draw_drivercard(p, tm, x_offset, y_offset, card_width, card_height)

        # Draw the second card (if it fits)
        second_card_x = x_offset + card_width + card_spacing_x
        if second_card_x + card_width <= A4[0] - margin:
            draw_drivercard(p, tm, second_card_x, y_offset, card_width, card_height)

        p.save()

        # Get the PDF content from the buffer
        pdf_content = buffer.getvalue()
        buffer.close()

        response.write(pdf_content)
        return response
