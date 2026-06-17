# Job Script Frontend

React + Vite frontend for the Job Script job market analysis dashboard.

## Tech Stack

- **React 18** - UI library
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **Recharts** - Simple charts
- **D3.js** - Complex visualizations
- **React Query** - Data fetching
- **React Router** - Navigation

## Setup

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Configure environment:
```bash
copy .env.example .env
# Edit .env with your API URL
```

3. Run development server:
```bash
npm run dev
```

The app will be available at http://localhost:5173

## Project Structure

```
frontend/
├── public/
│   └── target.svg          # Favicon
├── src/
│   ├── api/
│   │   └── index.js        # API client
│   ├── components/
│   │   ├── charts/
│   │   │   ├── Charts.jsx      # Recharts components
│   │   │   ├── NetworkGraph.jsx # D3 network graph
│   │   │   └── Heatmap.jsx     # D3 heatmap
│   │   ├── ui/
│   │   │   └── index.jsx       # UI components
│   │   └── Layout.jsx          # Main layout
│   ├── hooks/
│   │   └── useData.js          # React Query hooks
│   ├── pages/
│   │   ├── Dashboard.jsx
│   │   ├── SkillsPage.jsx
│   │   ├── SalaryPage.jsx
│   │   ├── CompaniesPage.jsx
│   │   ├── CareerPage.jsx
│   │   └── GlobalPage.jsx
│   ├── utils/
│   │   └── helpers.js          # Utility functions
│   ├── App.jsx
│   ├── main.jsx
│   └── index.css
├── package.json
├── vite.config.js
├── tailwind.config.js
└── postcss.config.js
```

## Features

- 📊 **Dashboard** - Overview of job market stats
- 🛠️ **Skills Analysis** - Top skills and co-occurrence
- 💰 **Salary Insights** - Salary premiums by skill
- 🏢 **Companies** - Top hiring companies
- 🔄 **Career Paths** - Role similarity and transitions
- 🌍 **Global Comparison** - Compare skills across countries

## Environment Variables

Create a `.env` file:

```
VITE_API_URL=http://localhost:8000/api/v1
```

For production:
```
VITE_API_URL=https://your-backend.render.com/api/v1
```

## Build for Production

```bash
npm run build
```

Output will be in the `dist/` folder.

## Deployment (Vercel)

1. Push code to GitHub
2. Connect repo to Vercel
3. Set environment variables:
   - `VITE_API_URL` = your backend URL
4. Deploy!

Vercel will auto-detect Vite and configure build settings.
