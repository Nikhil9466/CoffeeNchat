import { useEffect, useRef, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { MessageCircle, Users, LoaderCircle, X } from "lucide-react";
export type Notice = (text: string, bad?: boolean) => void;
export function Brand({ small = false }: { small?: boolean }) {
  return (
    <Link className="brand" to="/">
      <span className="brand-icon">
        <MessageCircle size={small ? 19 : 22} />
      </span>
      {!small && (
        <span>
          CoffeeNchat<span className="brand-dot">.</span>
        </span>
      )}
    </Link>
  );
}
export function Avatar({
  name,
  group = false,
}: {
  name: string;
  group?: boolean;
}) {
  return (
    <span className={"avatar " + (group ? "group-avatar" : "")}>
      {group ? <Users size={21} /> : name.slice(0, 2).toUpperCase()}
    </span>
  );
}
export function Loading() {
  return (
    <div className="loading">
      <LoaderCircle className="spin" /> Loading your workspace…
    </div>
  );
}
export function Modal({
  title,
  children,
  close,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      aria-label={title}
      onCancel={close}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="modal-header">
        <h2>{title}</h2>
        <button className="icon" aria-label="Close dialog" onClick={close}>
          <X />
        </button>
      </div>
      {children}
    </dialog>
  );
}
