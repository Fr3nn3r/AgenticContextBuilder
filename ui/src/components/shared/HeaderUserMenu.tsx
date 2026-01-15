import { useState, useRef, useEffect } from "react";
import { cn } from "../../lib/utils";
import { useAuth } from "../../context/AuthContext";

export function HeaderUserMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const { user, logout } = useAuth();

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setIsOpen(false);
    }

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      return () => document.removeEventListener("keydown", handleEscape);
    }
  }, [isOpen]);

  const handleLogout = async () => {
    setIsOpen(false);
    await logout();
  };

  if (!user) return null;

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex items-center gap-2 p-1.5 rounded-md transition-colors",
          isOpen
            ? "bg-accent"
            : "hover:bg-muted"
        )}
        title={`Signed in as ${user.username}`}
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        <div className="w-7 h-7 bg-primary rounded-full flex items-center justify-center text-sm font-medium text-primary-foreground">
          {user.username.charAt(0).toUpperCase()}
        </div>
        <ChevronDownIcon
          className={cn(
            "w-4 h-4 text-muted-foreground transition-transform",
            isOpen && "rotate-180"
          )}
        />
      </button>

      {isOpen && (
        <div
          className="absolute right-0 top-full mt-2 w-56 bg-popover border border-border rounded-lg shadow-lg py-2 z-50"
          role="menu"
        >
          {/* User Info Header */}
          <div className="px-3 py-2 border-b border-border mb-1">
            <div className="font-medium text-foreground">{user.username}</div>
            <div className="text-xs text-muted-foreground capitalize">{user.role}</div>
          </div>

          {/* Sign Out */}
          <div className="px-1">
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-3 py-2 text-sm rounded-md text-foreground hover:bg-muted transition-colors"
              role="menuitem"
            >
              <LogoutIcon className="w-4 h-4" />
              <span>Sign out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Icons
function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  );
}

function LogoutIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
      />
    </svg>
  );
}
