"use client";

import { useState } from "react";
import Image from "next/image";
import { CheckIcon } from "lucide-react";
import { Bubble, Label, Timestamp } from "@/components/landing/chat";
import oakTable from "@/components/landing/photos/oak-table.jpg";

type Reply = "approve" | "change" | null;

export function ApprovalDemo() {
  const [reply, setReply] = useState<Reply>(null);

  return (
    <>
      <Bubble from="neitor" className="max-w-120 overflow-hidden px-3.5 pt-3.5 pb-0 sm:max-w-120">
        <p className="mx-1.5 mt-0.5 mb-3">On it. Here&apos;s your post for Saturday:</p>
        <div className="overflow-hidden rounded-[18px] shadow-[0_0_0_1px_var(--color-ld-line)]">
          <div className="flex items-center gap-2.5 px-3 py-2.5">
            <span
              aria-hidden="true"
              className="flex size-8 items-center justify-center rounded-full bg-[#6b3e26] text-[13px] font-bold text-[#f2e6d3] ring-[1.5px] ring-ld-accent ring-offset-2"
            >
              R
            </span>
            <span className="flex flex-col">
              <span className="text-sm font-bold">roble.taller</span>
              <span className="text-xs font-medium text-ld-subtle">Montevideo</span>
            </span>
            <Label className="ml-auto">Example</Label>
          </div>
          <div className="bg-[#e9dcc6] px-5.5 pt-5.5 pb-6.5">
            <Image
              src={oakTable}
              alt="The owner's oak table, framed in the shop's brand colors"
              sizes="(min-width: 640px) 440px, 80vw"
              placeholder="blur"
              className="h-80 w-full rounded-md object-cover object-[50%_85%] shadow-[0_22px_34px_-20px_rgb(70_40_20/0.65)]"
            />
          </div>
          <p className="px-3.5 pt-3 pb-3.5 text-[15px] leading-snug">
            <strong>roble.taller</strong> Solid oak, finished by hand in our workshop. Our new round table is ready
            for its home: come see it this Saturday, 10 to 14.
          </p>
        </div>
        <Timestamp time="11:43 PM" className="mx-1 mt-2 mb-2.5" />
        {reply === null ? (
          <div className="-mx-3.5 flex">
            <button
              type="button"
              onClick={() => setReply("approve")}
              className="flex min-h-13 flex-1 items-center justify-center gap-2 border-t border-ld-line text-base font-bold text-ld-accent-ink transition-colors outline-none hover:bg-[#f5f8f5] focus-visible:bg-[#f5f8f5] focus-visible:ring-3 focus-visible:ring-ld-forest/40 focus-visible:ring-inset"
            >
              <CheckIcon className="size-4.5" strokeWidth={2.6} aria-hidden="true" />
              Approve
            </button>
            <button
              type="button"
              onClick={() => setReply("change")}
              className="flex min-h-13 flex-1 items-center justify-center border-t border-l border-ld-line text-base font-bold text-ld-forest transition-colors outline-none hover:bg-[#f5f8f5] focus-visible:bg-[#f5f8f5] focus-visible:ring-3 focus-visible:ring-ld-forest/40 focus-visible:ring-inset"
            >
              Change something
            </button>
          </div>
        ) : null}
      </Bubble>

      <div aria-live="polite">
        {reply === "approve" ? (
          <>
            <Bubble from="owner" time="11:44 PM" rowClassName="motion-safe:animate-rise">
              <strong>Approve</strong>
            </Bubble>
            <Bubble from="neitor" time="11:44 PM" rowClassName="motion-safe:animate-rise motion-safe:[animation-delay:.4s]">
              Done. It goes live <strong>Saturday at 10:00</strong> on your Instagram. Sleep well.
            </Bubble>
          </>
        ) : null}
        {reply === "change" ? (
          <>
            <Bubble from="owner" time="11:44 PM" rowClassName="motion-safe:animate-rise">
              <strong>Change something</strong>
            </Bubble>
            <Bubble from="neitor" time="11:44 PM" rowClassName="motion-safe:animate-rise motion-safe:[animation-delay:.4s]">
              Sure. Tell me what to change, by text or voice note: the photo, the words, the day. I&apos;ll send a new
              version.
            </Bubble>
          </>
        ) : null}
      </div>
    </>
  );
}
