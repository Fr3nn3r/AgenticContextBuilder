# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# IMPORTANT
- never EVER push to github unless the User explicitly tells you to.

# ACTIVE CONTRIBUTORS
- **User (Human)**: Works in Cursor IDE, directs the project, makes high-level decisions, has the best taste & judgement.
- **Cursor Agent**: AI copilot activated by User, lives in the Cursor IDE, medium level of autonomy, can edit multiple files at once, can run terminal commands, can access the whole codebase; the User uses it to vibe-code the app.
- **Claude Code**: Terminal-based AI agent with high autonomy, can edit multiple files simultaneously, understands entire codebase automatically, runs tests/Git operations, handles large-scale refactoring and complex debugging independently

## Development Commands

### Backend (Python FastAPI)
```bash
# Start backend development server
cd backend && uvicorn api:app --reload
```

### Frontend (Next.js)
```bash
# Start frontend development server
cd frontend/ && npm run dev

# Build for production
cd frontend/ && npm run build

# Lint code
cd frontend/ && npm run lint
```

## Architecture Overview

This is a full-stack AI Context Management Application built with Python FastAPI backend and Next.js frontend. 

The core architectural pattern is **Perspectives** - modular features that exist on both frontend and backend:

### Perspectives System
Each perspective represents a major app feature with corresponding frontend/backend implementations:
- **TaskListPerspective**: Task management and organization
- **ProjectsPerspective**: Project tracking and team coordination  
- **NoteListPerspective**: Note-taking with reminders and recurrence
- **StandardChatPerspective**: AI conversations and chat history
- **InfiniteThinkingPerspective**: Continuous AI reasoning and research
- **IdeasInboxPerspective**: Idea capture and organization

### Key Patterns
- **API Communication**: All perspectives use standardized endpoints:
  - `GET /perspective/{name}/get-screen-data` - Initial data loading
  - `POST /perspective/{name}/communicate` - Interactive communication with streaming
- **AI Agents**: Each perspective has specialized AI agents in `/backend/agents/`
- **State Management**: Redux for global state, React Context for UI state, Perspectives for feature state

## Technology Stack

### Backend
- **FastAPI** with Python 3.12
- **Supabase** (PostgreSQL) for database
- **OpenRouter** for AI model access (Claude, GPT, DeepSeek, O3)
- **dramatiq + Redis** for background jobs
- **Google Auth** integration

### Frontend  
- **Next.js 15.2.4** with TypeScript
- **Tailwind CSS** (dark mode default: #1A1A1A primary, #121212 secondary)
- **Redux Toolkit** + React Context for state
- **shadcn/ui** components (Radix UI primitives)
- **Framer Motion** for animations

## File Structure

### Backend (`/backend/`)
- **`api.py`**: FastAPI app entry point
- **`apis/`**: REST endpoints organized by feature
- **`agents/`**: AI agents with system prompts and logic
- **`perspectives/`**: Backend perspective implementations
- **`services/`**: Business logic layer
- **`database/`**: Supabase operations
- **`utils/`**: Shared utilities (LLMs, date, logging)

### Frontend (`/frontend/`)
- **`app/`**: Next.js app router pages
- **`components/`**: React components by feature
- **`lib/perspectives/`**: Frontend perspective implementations
- **`store/`**: Redux store and reducers
- **`hooks/`**: Custom React hooks

## Development Guidelines

### Code Standards (from .cursorrules)
- **Simplicity First**: Clean, modular code over complexity
- **Extensive Comments**: Explain WHY, not just WHAT - especially thought process
- **Header Comments**: Every file starts with 3 comments (location, purpose, scope)
- **No Feature Creep**: Execute exactly what's requested, nothing more
- **Never Auto-Push**: Only push to GitHub when explicitly requested

### UI Design Principles
- Dark mode default with neutral grays (never blue-tinted)
- Card-based layouts with subtle borders (#333333, #2C2C2C)
- Text hierarchy: white primary, neutral-300/400/500 secondary
- Extensive tooltips for context
- Responsive mobile-first design

### Anti-Complexity Philosophy
- BE VERY SUSPICIOUS OF EVERY COMPLICATION - simple = good, complex = bad
- Do exactly what's asked, nothing more
- Execute precisely what the user asks for, without additional features
- Constantly verify you're not adding anything beyond explicit instructions

### Comment Strategy
- Add a lot of comments into the code you write
- Explain WHY the code was added, not just WHAT it does
- Focus on explaining non-obvious stuff, nuances and details
- NEVER delete explanatory comments unless they are wrong/obsolete

### Communication Style
- Use simple & easy-to-understand language. write in short sentences
- Be CLEAR and STRAIGHT TO THE POINT
- EXPLAIN EVERYTHING CLEARLY & COMPLETELY
- Address ALL of user's points and questions clearly and completely.

## Environment Variables

### Backend (`.env`)
- `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_API_KEY`
- `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

### Frontend (`.env.local`)
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_API_URL` (backend URL)

## Key Implementation Notes

- **Branch Strategy**: `main` = production, `dev` = staging

## Testing & Quality

- Backend testing files in `/backend/test/`

# IMPORTANT
- never EVER push to github unless the User explicitly tells you to.