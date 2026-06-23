import * as Tooltip from "@radix-ui/react-tooltip";

import { glossary } from "../lib/glossary";

type AbbrProps = {
  term: keyof typeof glossary;
};

export function Abbr({ term }: AbbrProps) {
  return (
    <Tooltip.Provider delayDuration={150}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <abbr className="cursor-help decoration-dotted underline-offset-2" title={glossary[term]}>
            {term}
          </abbr>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            className="rounded bg-zinc-950 px-2 py-1 text-xs text-white shadow"
            sideOffset={4}
          >
            {glossary[term]}
            <Tooltip.Arrow className="fill-zinc-950" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}
