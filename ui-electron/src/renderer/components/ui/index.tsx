/**
 * UI 基础组件
 */

import React from "react";
import { Loader2 } from "lucide-react";

// ============================================================
// Button
// ============================================================

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: React.ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  children,
  className = "",
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`button button-${variant} button-${size} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <Loader2 size={14} className="spin" />
      ) : icon ? (
        <span className="button-icon">{icon}</span>
      ) : null}
      {children && <span className="button-text">{children}</span>}
    </button>
  );
}

// ============================================================
// Card
// ============================================================

interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: "none" | "sm" | "md" | "lg";
}

export function Card({ children, className = "", padding = "md" }: CardProps) {
  return (
    <div className={`card card-padding-${padding} ${className}`}>
      {children}
    </div>
  );
}

interface CardHeaderProps {
  children: React.ReactNode;
  actions?: React.ReactNode;
}

export function CardHeader({ children, actions }: CardHeaderProps) {
  return (
    <div className="card-header">
      <div className="card-header-content">{children}</div>
      {actions && <div className="card-header-actions">{actions}</div>}
    </div>
  );
}

export function CardTitle({ children }: { children: React.ReactNode }) {
  return <h3 className="card-title">{children}</h3>;
}

export function CardContent({ children }: { children: React.ReactNode }) {
  return <div className="card-content">{children}</div>;
}

// ============================================================
// Panel
// ============================================================

interface PanelProps {
  children: React.ReactNode;
  className?: string;
}

export function Panel({ children, className = "" }: PanelProps) {
  return <div className={`panel ${className}`}>{children}</div>;
}

interface PanelHeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export function PanelHeader({ title, subtitle, actions }: PanelHeaderProps) {
  return (
    <div className="panel-header">
      <div className="panel-header-text">
        <h2 className="panel-title">{title}</h2>
        {subtitle && <p className="panel-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="panel-header-actions">{actions}</div>}
    </div>
  );
}

export function PanelContent({ children }: { children: React.ReactNode }) {
  return <div className="panel-content">{children}</div>;
}

export function PanelActions({ children }: { children: React.ReactNode }) {
  return <div className="panel-actions">{children}</div>;
}

// ============================================================
// Status Pill
// ============================================================

interface StatusPillProps {
  status: string;
  size?: "sm" | "md";
  className?: string;
}

export function StatusPill({ status, size = "md", className = "" }: StatusPillProps) {
  const normalized = status.toLowerCase().replace(/[_-]/g, "");
  return (
    <span className={`status-pill status-${normalized} size-${size} ${className}`}>
      {status}
    </span>
  );
}

// ============================================================
// Progress Bar
// ============================================================

interface ProgressBarProps {
  value: number;
  max?: number;
  size?: "sm" | "md" | "lg";
  variant?: "default" | "success" | "warning" | "error";
  showLabel?: boolean;
  className?: string;
}

export function ProgressBar({
  value,
  max = 100,
  size = "md",
  variant = "default",
  showLabel = false,
  className = "",
}: ProgressBarProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  return (
    <div className={`progress progress-${size} ${className}`}>
      <div
        className={`progress-bar progress-${variant}`}
        style={{ width: `${percentage}%` }}
      />
      {showLabel && (
        <span className="progress-label">{Math.round(percentage)}%</span>
      )}
    </div>
  );
}

// ============================================================
// Loading Spinner
// ============================================================

interface LoadingSpinnerProps {
  size?: number;
  className?: string;
}

export function LoadingSpinner({ size = 24, className = "" }: LoadingSpinnerProps) {
  return (
    <div className={`loading-spinner ${className}`}>
      <Loader2 size={size} className="spin" />
    </div>
  );
}

// ============================================================
// Empty State
// ============================================================

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      {icon && <div className="empty-state-icon">{icon}</div>}
      <h3 className="empty-state-title">{title}</h3>
      {description && <p className="empty-state-description">{description}</p>}
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  );
}

// ============================================================
// Alert
// ============================================================

interface AlertProps {
  variant?: "info" | "success" | "warning" | "error";
  title?: string;
  children: React.ReactNode;
  onClose?: () => void;
}

export function Alert({
  variant = "info",
  title,
  children,
  onClose,
}: AlertProps) {
  return (
    <div className={`alert alert-${variant}`}>
      {title && <div className="alert-title">{title}</div>}
      <div className="alert-content">{children}</div>
      {onClose && (
        <button className="alert-close" onClick={onClose}>
          ×
        </button>
      )}
    </div>
  );
}

// ============================================================
// Tag Input
// ============================================================

interface TagInputProps {
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  variant?: "default" | "allow" | "deny" | "command";
  disabled?: boolean;
}

export function TagInput({
  tags,
  onChange,
  placeholder = "输入并按回车",
  variant = "default",
  disabled = false,
}: TagInputProps) {
  const [input, setInput] = React.useState("");

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && input.trim()) {
      e.preventDefault();
      if (!tags.includes(input.trim())) {
        onChange([...tags, input.trim()]);
      }
      setInput("");
    } else if (e.key === "Backspace" && !input && tags.length > 0) {
      onChange(tags.slice(0, -1));
    }
  };

  const removeTag = (index: number) => {
    onChange(tags.filter((_, i) => i !== index));
  };

  return (
    <div className={`tag-input tag-input-${variant} ${disabled ? "disabled" : ""}`}>
      <div className="tag-list">
        {tags.map((tag, index) => (
          <span key={`${tag}-${index}`} className="tag">
            {tag}
            {!disabled && (
              <button
                type="button"
                className="tag-remove"
                onClick={() => removeTag(index)}
              >
                ×
              </button>
            )}
          </span>
        ))}
      </div>
      <input
        type="text"
        className="tag-input-field"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={tags.length === 0 ? placeholder : ""}
        disabled={disabled}
      />
    </div>
  );
}

// ============================================================
// Dropdown
// ============================================================

interface DropdownProps {
  trigger: React.ReactNode;
  children: React.ReactNode;
  align?: "left" | "right";
}

export function Dropdown({ trigger, children, align = "left" }: DropdownProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  return (
    <div ref={ref} className={`dropdown ${isOpen ? "open" : ""}`}>
      <div className="dropdown-trigger" onClick={() => setIsOpen(!isOpen)}>
        {trigger}
      </div>
      {isOpen && (
        <div className={`dropdown-menu dropdown-${align}`}>
          {children}
        </div>
      )}
    </div>
  );
}

interface DropdownItemProps {
  onClick: () => void;
  children: React.ReactNode;
  danger?: boolean;
}

export function DropdownItem({ onClick, children, danger }: DropdownItemProps) {
  return (
    <button
      className={`dropdown-item ${danger ? "danger" : ""}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
