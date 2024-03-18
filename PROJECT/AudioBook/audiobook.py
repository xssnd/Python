from gtts import gTTS
import pdfplumber

# Open PDF file
with open('sample.pdf', 'rb') as pdf_file:
    # Create PDF Plumber object
    pdf = pdfplumber.open(pdf_file)
    
    # Initialize text string
    text_string = ""
    
    # Extract text from each page
    for page in pdf.pages:
        text_string += page.extract_text()
    
    # Close PDF
    pdf.close()

# Set Languages to English (en)
language = 'en'

# Call GTTS
myAudio = gTTS(text=text_string, lang=language, slow=False)

# Save as mp3 file
myAudio.save("Audio.mp3")

print("Audio file saved successfully.")