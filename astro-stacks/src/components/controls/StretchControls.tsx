import { useEffect, useState } from "react";
import { Button } from "@chakra-ui/react";
import { getHistogram } from "../../api/client";
import type { Histogram as HistogramData, StretchMethod, StretchParams, TransformParams } from "../../api/types";
import { FieldLabel } from "./FieldLabel";
import { Histogram } from "./Histogram";
import { LabeledSlider } from "./LabeledSlider";
import { TabDescription } from "./TabDescription";
import styles from "./StretchControls.module.scss";

const METHODS: { value: StretchMethod; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "mtf", label: "MTF" },
  { value: "asinh", label: "Asinh" },
];

export function StretchControls({
  params,
  onChange,
  workspaceId,
  masterLoaded,
  transformParams,
}: {
  params: StretchParams;
  onChange: (params: StretchParams) => void;
  workspaceId: string;
  masterLoaded: boolean;
  transformParams: TransformParams;
}) {
  const [histogram, setHistogram] = useState<HistogramData | null>(null);

  // The histogram reflects the linear data itself (which region of the
  // frame, via rotation/crop) -- not the stretch method/midtone/target_bkg,
  // so this only needs to refetch on those, plus shadow_clip since that's
  // what the black-point marker is drawn from.
  useEffect(() => {
    if (!masterLoaded) {
      setHistogram(null);
      return;
    }
    getHistogram(workspaceId, params.shadow_clip, transformParams)
      .then(setHistogram)
      .catch(() => setHistogram(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, masterLoaded, params.shadow_clip, transformParams]);

  return (
    <div className={styles.section}>
      <TabDescription>
        Controls how the stacked master's very high dynamic range is compressed into a viewable image. The master
        file itself is never modified -- this only affects the live preview, saved versions, and export at the
        moment they're generated.
      </TabDescription>

      <Histogram data={histogram} />

      <div className={styles.field}>
        <FieldLabel
          label="Stretch method"
          tooltip="Auto: picks black point and midtone automatically from the image's own statistics -- the best starting point for most stacks. MTF: manual midtone transfer function, set the pivot point yourself via the Midtone slider. Asinh: an inverse hyperbolic sine stretch, gentler on bright star cores at high contrast -- set via the Asinh scale slider."
        />
        <div className={styles.segmented}>
          {METHODS.map((m) => (
            <Button
              key={m.value}
              size="sm"
              variant={params.method === m.value ? "solid" : "outline"}
              colorPalette="brand"
              onClick={() => onChange({ ...params, method: m.value })}
            >
              {m.label}
            </Button>
          ))}
        </div>
      </div>

      {params.method === "auto" && (
        <div className={styles.field}>
          <LabeledSlider
            label="Target background"
            tooltip="Nudges how bright the sky background reads in the auto stretch. The black point and midtone are still derived from the image's own statistics -- this only shifts the overall brightness target, higher pulls faint signal further out of the background."
            value={params.target_bkg}
            min={0.05}
            max={0.5}
            step={0.005}
            precision={3}
            onChange={(target_bkg) => onChange({ ...params, target_bkg })}
          />
        </div>
      )}

      {params.method === "mtf" && (
        <div className={styles.field}>
          <LabeledSlider
            label="Midtone"
            tooltip="The midtone transfer function's pivot point (0-1, on the normalized linear data). Lower values push more of the faint signal into the midtones, brightening the image; higher values keep more of it compressed near black."
            value={params.midtone}
            min={0.01}
            max={0.9}
            step={0.005}
            precision={3}
            onChange={(midtone) => onChange({ ...params, midtone })}
          />
        </div>
      )}

      {params.method === "asinh" && (
        <div className={styles.field}>
          <LabeledSlider
            label="Asinh scale"
            tooltip="Controls how aggressively the asinh stretch compresses bright values. Lower scale = a gentler, more linear-looking stretch; higher scale = faint signal is pulled up more aggressively while bright star cores stay controlled."
            value={params.scale}
            min={10}
            max={5000}
            step={10}
            precision={0}
            onChange={(scale) => onChange({ ...params, scale })}
          />
        </div>
      )}
    </div>
  );
}
