import { createElement } from "react";
import type { IconNode } from "lucide";

export function Icon({
  node,
  size,
  color,
  strokeWidth = 2,
}: {
  node: IconNode;
  size: number;
  color: string;
  strokeWidth?: number;
}) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {node.map(([tag, attributes], position) => createElement(tag, { key: position, ...attributes }))}
    </svg>
  );
}
