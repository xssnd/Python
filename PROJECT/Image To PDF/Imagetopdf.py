from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PIL import Image

def convert_to_pdf(image_path, output_path):
    # Open the image using PIL
    img = Image.open(image_path)

    # Create a PDF Document
    c = canvas.Canvas(output_path, pagesize=letter)

    # Draw the image on PDF
    c.drawImage(image_path, 0, 0, width=letter[0], height=letter[1])

    # Save the PDF
    c.save()

image_path = "Images_Example.jpg"
output_path = "output.pdf"
convert_to_pdf(image_path, output_path)