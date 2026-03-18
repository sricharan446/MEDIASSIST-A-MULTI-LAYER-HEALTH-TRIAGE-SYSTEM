# AI Agent - Single Server Setup

## ✅ What Changed
- **Before**: 2 servers needed (backend on port 8000 + frontend on port 3000)
- **Now**: Just 1 Python file! Open http://mediassist.local and you're done

---

## 📋 Requirements
- Python 3.9 or higher
- An Anthropic API Key

---

## 🚀 Setup (3 Easy Steps)

### Step 1: Install Packages
Open your terminal/command prompt inside this folder and run:

**Windows:**
```
pip install -r requirements.txt
```

**Mac/Linux:**
```
pip3 install -r requirements.txt
```

---

### Step 2: Add Your API Key

1. Find the file called `.env.example`
2. Rename it to `.env`
3. Open `.env` with Notepad (Windows) or any text editor
4. Replace `your_api_key_here` with your actual Anthropic API key:
   ```
   ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxx
   ```
5. Save the file

---

### Step 3: Run the App

**Windows:**
```
python app.py
```

**Mac/Linux:**
```
python3 app.py
```

You'll see:
```
==================================================
  AI Agent Assistant - Single Server
==================================================

✅ API Key loaded

🚀 Starting server...
   Open your browser: http://mediassist.local

   Press CTRL+C to stop
==================================================
```

---

## 🌐 Open in Browser

Go to: **http://mediassist.local**

That's it! No second terminal, no Node.js, no npm needed.

---

## 🛑 To Stop

Press `CTRL + C` in your terminal

---

## ❌ Common Errors

**"No module named 'fastapi'"**
→ Run: `pip install -r requirements.txt`

**"ANTHROPIC_API_KEY not found"**
→ Make sure your `.env` file exists and has your key

**"Port already in use"**
→ Restart your computer or change PORT=8001 in `.env`
