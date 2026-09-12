# SmartPostAI - Python AI Agent & REST Backend ⚙️

SmartPostAI Backend is built using `uAgents` and Python 3.11, providing AI content generation, automated post scheduling, Supabase authentication, and LinkedIn API integration.

![Render Deployment](https://img.shields.io/badge/Render-Live_API-46E3B7?style=for-the-badge&logo=render)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python)
![uAgents](https://img.shields.io/badge/uAgents-0.23-blue?style=for-the-badge)
![Supabase](https://img.shields.io/badge/Supabase-Database-3ECF8E?style=for-the-badge&logo=supabase)

---

## 🌐 Live Deployments

- ⚙️ **Production REST API**: [https://smartpost-backend.onrender.com](https://smartpost-backend.onrender.com)
- 🎨 **Frontend Web App**: [https://smart-post-ai-frontend.vercel.app](https://smart-post-ai-frontend.vercel.app)

---

## 📡 API Endpoints Summary

- `GET /api/health` - Health check & server status
- `POST /auth/login` - Supabase user authentication login
- `POST /auth/signup` - User account registration
- `GET /linkedin/connect` - Generate LinkedIn OAuth URL
- `GET /linkedin/callback` - Handle LinkedIn OAuth callback redirect
- `POST /api/ai/generate` - AI post generation via Google Gemini

---

## 📄 License

MIT License
