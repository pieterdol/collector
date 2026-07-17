import type { ReactNode } from "react";
import { LogoIcon } from "./icons";

interface Props {
  title: string;
  message: string;
  action?: ReactNode;
}

export function EmptyState({ title, message, action }: Props) {
  return (
    <div className="py-20 text-center text-muted">
      <div className="mx-auto mb-5 grid h-19 w-19 place-items-center rounded-[22px] bg-surface text-faint" style={{ width: 76, height: 76 }}>
        <LogoIcon size={30} />
      </div>
      <h3 className="m-0 mb-1.5 text-[19px] font-extrabold tracking-tight text-text">{title}</h3>
      <p className="m-0 mb-5 text-sm">{message}</p>
      {action}
    </div>
  );
}
