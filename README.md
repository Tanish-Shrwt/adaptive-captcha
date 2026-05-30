# Adaptive CAPTCHA System

An intelligent multi-layer CAPTCHA system that dynamically adjusts challenge difficulty based on user behavior and bot probability. The project combines traditional CAPTCHA methods with behavioral analysis to create a more secure and user-friendly authentication experience.

---

## Features

* Adaptive difficulty adjustment based on user interactions
* Real-time bot probability calculation
* Multiple CAPTCHA types integrated into a single system
* Human-friendly validation flow with gradual difficulty escalation
* Behavioral analysis using failed attempts and interaction patterns
* Interactive and responsive frontend interface

---

## CAPTCHA Types Implemented

### 1. Image Tile CAPTCHA

Users select correct image tiles based on the given prompt.

### 2. Audio CAPTCHA

Audio-based verification for accessibility and alternative validation.

### 3. Math CAPTCHA

Users solve dynamically generated mathematical expressions.

### 4. Drag and Drop CAPTCHA

Interactive drag-and-drop challenge for human verification.

### 5. Rotation CAPTCHA

Users rotate images to the correct orientation.

---

## Adaptive CAPTCHA Flow

1. User enters the system
2. Initial CAPTCHA challenge is generated
3. User behavior is analyzed in real time
4. Bot probability score is calculated
5. Difficulty level changes dynamically:

   * Low risk → easier CAPTCHA
   * Medium risk → moderate CAPTCHA
   * High risk → advanced CAPTCHA
6. Correct responses reduce risk score gradually
7. Repeated failures increase bot probability

---

## Tech Stack

### Frontend

* HTML
* CSS
* JavaScript

### Backend

* Python
* Flask

### Additional Technologies

* OpenCV
* NumPy
* CAPTCHA generation libraries

---

## Project Structure

```bash
adaptive-captcha/
│
├── static/
│   ├── css/
│   ├── js/
│   ├── images/
│
├── templates/
│   ├── index.html
│   ├── captcha_pages/
│
├── backend/
│   ├── app.py
│   ├── captcha_logic/
│   ├── risk_analysis/
│
├── datasets/
├── requirements.txt
└── README.md
```

---

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/adaptive-captcha.git
```

### 2. Navigate to Project Directory

```bash
cd adaptive-captcha
```

### 3. Create Virtual Environment

```bash
python -m venv venv
```

### 4. Activate Virtual Environment

#### Windows

```bash
venv\Scripts\activate
```

#### Linux / Mac

```bash
source venv/bin/activate
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Run the Application

```bash
python app.py
```

---

## Working Principle

The system continuously tracks user interaction patterns such as:

* Wrong CAPTCHA attempts
* Time taken to solve challenges
* Mouse interaction behavior
* Accuracy of responses
* Sequential failure patterns

Using these factors, the system dynamically updates the bot probability score and assigns appropriate CAPTCHA difficulty levels.

---

## Applications

* Secure Login Systems
* Banking & Financial Platforms
* E-commerce Websites
* Government Portals
* Online Examination Systems
* AI Bot Prevention Systems

---

## Future Scope

* AI-based behavioral analysis
* Integration with biometric verification
* Machine learning based risk prediction
* Advanced anti-bot analytics dashboard

---

## Screenshots

Add project screenshots here.

```bash
README Images/
```

Example:

```md
![Home Page](images/home.png)
```

