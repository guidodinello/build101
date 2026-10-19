"use client";

import { CheckIcon } from "lucide-react";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

type ChoiceChipsProps = {
  options: { value: string; label: string }[];
  value: string[];
  onChange: (value: string[]) => void;
  multiple?: boolean;
  max?: number;
  invalid?: boolean;
  "aria-label"?: string;
  "aria-labelledby"?: string;
};

export function ChoiceChips({
  options,
  value,
  onChange,
  multiple = false,
  max,
  invalid = false,
  ...labelling
}: ChoiceChipsProps) {
  const full = max !== undefined && value.length >= max;

  return (
    <ToggleGroup
      {...labelling}
      multiple={multiple}
      variant="chip"
      size="lg"
      className="flex-wrap"
      aria-invalid={invalid || undefined}
      value={value}
      onValueChange={(next: string[]) => {
        if (!multiple && next.length === 0) return;
        onChange(max !== undefined ? next.slice(0, max) : next);
      }}
    >
      {options.map((option) => {
        const pressed = value.includes(option.value);
        return (
          <ToggleGroupItem key={option.value} value={option.value} disabled={full && !pressed}>
            {pressed && <CheckIcon data-icon="inline-start" className="stroke-3" />}
            {option.label}
          </ToggleGroupItem>
        );
      })}
    </ToggleGroup>
  );
}

export const asOptions = (labels: string[]) => labels.map((label) => ({ value: label, label }));
