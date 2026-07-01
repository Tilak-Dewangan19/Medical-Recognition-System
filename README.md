# 🩺 Medicine Recognition System

A web-based AI-powered medical image analysis platform that allows users to upload clinical images and receive structured, medically relevant descriptions using Google Gemini models.

## 🚀 Try it on

https://medical-recognition-system.onrender.com

## ✨ Features

### 🧑‍⚕️ Medical Image Analysis
- Upload medical images through an intuitive web interface.
- Generate structured AI analysis with sections such as:
  - Medical Image Description
  - Visual Findings
  - Possible Medical Relevance
  - Practical Guidance
  - When Professional Care Should Be Sought
  - Conclusion

### 🤖 AI-Powered Insights
- Uses Google Gemini vision models to interpret uploaded images.
- Includes fallback model support to improve reliability during rate limits or temporary service issues.

### 🔒 Secure & Practical
- Supports common image formats and DICOM-based medical files.
- Uses environment variables for secure API key management.
- Encourages cautious, non-diagnostic guidance for users.

## 🛠️ Tech Stack

| Layer | Technologies |
|------|--------------|
| **Frontend** | HTML, CSS, Jinja2 |
| **Backend** | Python, Flask |
| **AI / ML** | Google Gemini API (GenAI) |
| **Image Processing** | Pillow, pydicom |
| **Environment & Deployment** | python-dotenv, Gunicorn |

## 📁 Project Structure

```bash
Medicine-Recognition-System/
├── app.py                   # Main Flask application and analysis logic
├── templates/               # HTML templates for UI
├── static/                  # Static assets and uploaded images
├── tests/                   # Unit tests
├── requirements.txt         # Python dependencies
└── README.md                # Project documentation
```

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- pip
- A valid Google Gemini API key

### 1. Clone the repository

```bash
git clone https://github.com/your-username/Medicine-Recognition-System.git
cd Medicine-Recognition-System
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_FALLBACK=gemini-2.5-pro
```

### 5. Run the application

```bash
python app.py
```

Open your browser and visit:

```text
http://127.0.0.1:5000
```

## 📡 How it Works

1. User uploads a medical image through the web interface.
2. The backend validates the file and loads the image.
3. The Gemini model analyzes the image and generates a structured report.
4. The user receives medically relevant guidance in a safe, non-diagnostic format.

## 📝 Notes

- This application is intended for informational and educational purposes only.
- The generated output is not a substitute for professional medical diagnosis.
- Always consult a qualified healthcare professional for medical advice.

## 🤝 Contributing

Contributions are welcome. Please fork the repository, create a feature branch, and submit a pull request.

## 📄 License

This project is licensed under the GNU General Public License v3.0.

## 📞 Contact

For questions or suggestions, feel free to contact the repository maintainer.

