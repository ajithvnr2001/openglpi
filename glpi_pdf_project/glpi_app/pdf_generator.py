import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import boto3
from botocore.exceptions import ClientError
from typing import List, Dict

class PDFGenerator:
    _styles_setup = False  # Class-level variable

    def __init__(self, filename: str):
        self.filename = filename
        self.doc = SimpleDocTemplate(self.filename, pagesize=letter)
        self.styles = getSampleStyleSheet()
        if not PDFGenerator._styles_setup:  # Check if styles are already set up
            self.setup_styles()
            PDFGenerator._styles_setup = True # Set the flag

        # Wasabi S3 Configuration
        self.s3_client = boto3.client(
            's3',
            endpoint_url=os.environ.get("WASABI_ENDPOINT_URL"),
            aws_access_key_id=os.environ.get("WASABI_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("WASABI_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("WASABI_REGION") #optional
        )
        self.bucket_name = os.environ.get("WASABI_BUCKET_NAME")
        if not all([self.bucket_name, self.s3_client]):
           raise ValueError("Wasabi S3 environment variables not set.")

    def setup_styles(self):
        """Define custom paragraph styles."""
        self.styles.add(ParagraphStyle(name='Heading1',
                                      parent=self.styles['Heading1'],
                                      fontSize=16,
                                      spaceAfter=12))
        self.styles.add(ParagraphStyle(name='Heading2',
                                      parent=self.styles['Heading2'],
                                      fontSize=14,
                                      spaceBefore=10,
                                      spaceAfter=6))
        self.styles.add(ParagraphStyle(name='Normal_C',
                                      parent=self.styles['Normal'],
                                        alignment=TA_CENTER,
                                        spaceAfter=6))

        self.styles.add(ParagraphStyle(name='Bullet',
                                      parent=self.styles['Normal'],
                                        bulletIndent=18,
                                      leftIndent=36,
                                      spaceBefore=3,
                                      spaceAfter=3))


    def generate_report(self, title: str, query: str, result: str, source_info: List[Dict]):
        """Generates a PDF report with ReportLab and uploads to Wasabi S3."""
        elements = []

        # Title
        elements.append(Paragraph(title, self.styles['Heading1']))
        elements.append(Spacer(1, 0.2*inch))

        # Query
        elements.append(Paragraph(f"<b>Query:</b> {query}", self.styles['Heading2']))
        elements.append(Spacer(1, 0.1*inch))

        # Result (Process for potential bullet points)
        elements.append(Paragraph(f"<b>Result:</b>", self.styles['Heading2']))
        self.add_content_with_bullets(elements, result)
        elements.append(Spacer(1, 0.2*inch))

        # Source Information
        elements.append(Paragraph("<b>Source Information:</b>", self.styles['Heading2']))
        for source in source_info:
            elements.append(Paragraph(f"Source ID: {source.get('source_id', 'N/A')}", self.styles['Normal']))
            elements.append(Paragraph(f"Source Type: {source.get('source_type', 'N/A')}", self.styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))

        try:
          # Build PDF
          self.doc.build(elements)
          # Upload to Wasabi
          self.upload_to_s3(self.filename)
          print(f"PDF generated and uploaded to Wasabi S3: {self.filename}")

        except ClientError as e:
            print(f"S3 Upload Error: {e}")
        except Exception as e:
            print(f"Error generating or uploading PDF: {e}")

        finally:
            if os.path.exists(self.filename):
                os.remove(self.filename)

    def upload_to_s3(self, filename: str):
        """Uploads a file to the configured Wasabi S3 bucket."""
        try:
            self.s3_client.upload_file(filename, self.bucket_name, filename)
            print(f"File '{filename}' uploaded to Wasabi S3 bucket '{self.bucket_name}'")
        except ClientError as e:
            print(f"Error uploading to S3: {e}")
            raise

    def add_content_with_bullets(self, elements, text):
        """Adds content to the PDF, handling potential bullet points."""
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith(("* ", "- ")):  # Simple bullet point detection
                elements.append(Paragraph(line[2:].strip(), self.styles['Bullet'])) #remove "* "
            else:
                elements.append(Paragraph(line, self.styles['Normal']))
