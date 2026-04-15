# 🚀 Smart Vyapar - AI Business OS

The ChatGPT for shopkeepers. An AI-powered business operating system designed for local retailers to manage inventory, forecast demand, and optimize supplier relationships using autonomous AI agents.

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![React](https://img.shields.io/badge/React-18.3-blue.svg)
![Vite](https://img.shields.io/badge/Vite-6.0-purple.svg)

## ✨ Features

### 🏪 Core Functionality
- **AI-Powered Dashboard**: Real-time business insights and metrics
- **Smart Inventory Management**: Track stock levels with AI-powered reorder recommendations
- **Intelligent Order System**: Automated purchase order generation and supplier management
- **Predictive Analytics**: AI forecasting for sales trends and demand patterns
- **Supplier Negotiation**: AI agents that negotiate best prices autonomously
- **Settings & Customization**: Flexible configuration for shop details and AI agent permissions

### 🤖 AI Agent System
- **Inventory Agent**: Monitors stock levels and predicts shortages
- **Forecast Agent**: Analyzes trends and predicts future demand
- **Supplier Agent**: Manages supplier relationships and negotiations
- **Pricing Agent**: Optimizes product pricing based on market conditions
- **Analytics Agent**: Generates actionable insights from business data

### 💬 AI Chat Assistant
- **Persistent Chat Panel**: Collapsible 30% width panel on the right
- **Contextual Conversations**: Ask questions about specific products, orders, or insights
- **Suggested Prompts**: Quick access to common queries
- **Live Agent Activity**: See which AI agents are currently working

## 🛠️ Tech Stack

- **Framework**: React 18.3 + Vite 6.0
- **Styling**: TailwindCSS + ShadCN/UI Components
- **State Management**: Zustand
- **Routing**: React Router DOM
- **Charts**: Recharts
- **Animations**: Framer Motion
- **Agent Visualization**: React Flow
- **Notifications**: React Hot Toast
- **Icons**: Lucide React

## 📁 Project Structure

```
src/
 ┣ components/
 ┃ ┣ ChatPanel/          # AI Chat Assistant
 ┃ ┣ ui/                 # ShadCN UI components
 ┃ ┣ Sidebar.jsx         # Navigation sidebar
 ┃ ┗ DashboardLayout.jsx # Main layout wrapper
 ┣ pages/
 ┃ ┣ Landing/            # Landing page
 ┃ ┣ Dashboard/          # Main dashboard
 ┃ ┣ Inventory/          # Inventory management
 ┃ ┣ Orders/             # Orders & suppliers
 ┃ ┣ Insights/           # Analytics & AI insights
 ┃ ┣ Settings/           # Configuration
 ┃ ┗ Agents/             # AI agent visualization
 ┣ store/
 ┃ ┗ useChatStore.js     # Zustand store
 ┣ routes/
 ┃ ┗ AppRoutes.jsx       # Route configuration
 ┣ App.jsx
 ┣ main.jsx
 ┗ index.css
```

## 🚀 Getting Started

### Prerequisites
- Node.js (v18 or higher)
- npm or yarn

### Installation

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Start development server**
   ```bash
   npm run dev
   ```

3. **Open your browser**
   ```
   http://localhost:5173
   ```

### Build for Production

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

## 🎨 Key Components

### DashboardLayout
Main layout component that includes:
- Left Sidebar (15% width) - Navigation
- Main Content Area (flexible) - Page content
- Chat Panel (30% width, collapsible) - AI Assistant

### ChatPanel
- Persistent across all dashboard pages
- Collapsible with smooth animations
- Contextual message history
- Suggested prompts for quick actions
- Real-time agent activity indicators

### Pages

#### 1. Landing Page (`/`)
- Hero section with animated dashboard preview
- Features showcase
- Testimonials
- FAQ section
- CTA buttons

#### 2. Dashboard (`/dashboard`)
- Sales overview cards
- Sales trend charts
- AI recommendations carousel
- Task checklist

#### 3. Inventory (`/inventory`)
- Product table with search & filter
- Stock status indicators
- Add product modal
- Quick "Ask Agent" action for each product

#### 4. Orders (`/orders`)
- **Tabs**: Purchase Orders, Suppliers, Deliveries
- Supplier cards with ratings
- "Negotiate Price" AI feature
- Delivery tracking

#### 5. Insights (`/insights`)
- 4 interactive charts (Sales, Demand, Stock, Forecast)
- AI insights feed with priority levels
- Click charts to ask AI for analysis

#### 6. Settings (`/settings`)
- **Tabs**: Shop Info, Automation, AI Agents, Preferences
- Toggle automation features
- Configure agent permissions
- Language & currency settings
- Data export functionality

#### 7. Agents (`/agents`)
- React Flow visualization of agent network
- Agent status cards
- Activity timeline
- Real-time agent metrics

## 🎯 Usage Examples

### Ask AI About a Product
```javascript
// From Inventory page
<Button onClick={() => handleAskAgent(product)}>
  <MessageSquare /> Ask Agent
</Button>
```

### Toggle Chat Panel
```javascript
import useChatStore from '@/store/useChatStore';

const { toggleChatPanel } = useChatStore();
toggleChatPanel();
```

### Add Message to Chat
```javascript
const { addMessage } = useChatStore();

addMessage({
  role: 'user',
  content: 'What should I restock this week?'
});
```

## 🎨 Customization

### Theme Colors
Edit `src/index.css` to customize the color scheme:
```css
:root {
  --primary: 240 5.9% 10%;
  --secondary: 240 4.8% 95.9%;
  /* ... */
}
```

### Adding New Pages
1. Create page component in `src/pages/`
2. Add route in `src/routes/AppRoutes.jsx`
3. Add navigation link in `src/components/Sidebar.jsx`

### Adding New AI Agents
1. Add agent configuration in `src/pages/Agents/Agents.jsx`
2. Create corresponding node in React Flow
3. Add agent logic in backend (when integrated)

## 🔌 Backend Integration

This frontend is ready to integrate with a backend API. Key integration points:

- **Chat**: Connect `useChatStore` to WebSocket or REST API
- **Data**: Replace mock data with API calls using React Query
- **Authentication**: Add auth provider and protected routes
- **Real-time Updates**: Connect agents to live data streams

## 📱 Responsive Design

- **Desktop**: Full layout with sidebar + content + chat panel
- **Tablet**: Collapsible sidebar, full chat panel
- **Mobile**: Drawer navigation, overlay chat

## 🐛 Known Issues

- CSS lint warnings for `@tailwind` and `@apply` are expected (TailwindCSS directives)
- These warnings don't affect build or functionality

## 🤝 Contributing

This is a complete frontend template ready for:
- Backend API integration
- Real AI agent implementation
- Enhanced data visualization
- Additional features and pages

## 📄 License

Private project - All rights reserved

## 👨‍💻 Author

Built with ❤️ for local shopkeepers

---

**Need help?** Open an issue or contact support.
