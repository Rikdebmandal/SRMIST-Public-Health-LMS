'use client';

/**
 * Chart wrappers. One palette, one set of axis conventions, so every chart in
 * the platform reads as part of the same system in both light and dark mode.
 */
import { useTheme } from 'next-themes';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';

/**
 * Categorical palettes, distinguishable for common colour-vision deficiency.
 *
 * Dark mode needs more luminous hues to hold the same perceived contrast
 * against a dark card, so each theme gets its own ramp rather than one fixed
 * palette that reads as muddy on one side.
 */
const LIGHT_SERIES = [
  '#0b6e8f',
  '#1c7c54',
  '#c2620a',
  '#7b4fa8',
  '#a8324a',
  '#4a6fa5',
  '#6b7a35',
];

const DARK_SERIES = [
  '#4bb8dd',
  '#4fc08a',
  '#f0a24b',
  '#b98cf0',
  '#f07a92',
  '#8fb0e8',
  '#b6c96a',
];

const LIGHT_TONES = {
  ok: '#1c7c54',
  warning: '#c2620a',
  critical: '#b3261e',
  low: '#1c7c54',
  moderate: '#c2620a',
  high: '#d1451b',
  neutral: '#64748b',
} as const;

const DARK_TONES = {
  ok: '#4fc08a',
  warning: '#f0a24b',
  critical: '#f2665c',
  low: '#4fc08a',
  moderate: '#f0a24b',
  high: '#f4784f',
  neutral: '#94a3b8',
} as const;

/** Light-theme values, for callers that need a colour outside a render pass. */
export const SERIES_COLORS = LIGHT_SERIES;
export const TONE_COLORS = LIGHT_TONES;

/** Tone colours for the active theme, for pages that pass explicit colours. */
export function useToneColors() {
  return usePalette().tones;
}

function usePalette() {
  const { resolvedTheme } = useTheme();
  const dark = resolvedTheme === 'dark';
  return {
    series: dark ? DARK_SERIES : LIGHT_SERIES,
    tones: (dark ? DARK_TONES : LIGHT_TONES) as Record<string, string>,
  };
}

const axisProps = {
  stroke: 'currentColor',
  fontSize: 11,
  tickLine: false,
  axisLine: false,
  className: 'text-muted-foreground',
} as const;

function ChartTooltip({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs shadow-lg">
      {label !== undefined && <p className="mb-1 font-medium">{label}</p>}
      {payload.map((entry: any) => (
        <p key={entry.dataKey ?? entry.name} className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: entry.color ?? entry.fill }}
          />
          <span className="text-muted-foreground">{entry.name}:</span>
          <span className="font-medium tabular-nums">
            {typeof entry.value === 'number' ? entry.value.toFixed(1) : entry.value}
            {unit ?? ''}
          </span>
        </p>
      ))}
    </div>
  );
}

export function ChartFrame({
  height = 260,
  children,
}: {
  height?: number;
  children: React.ReactElement;
}) {
  return (
    <div style={{ width: '100%', height }} className="text-muted-foreground">
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}

export function TrendChart({
  data,
  xKey,
  yKey,
  label,
  referenceValue,
  referenceLabel,
  height = 240,
  unit = '%',
}: {
  data: Record<string, any>[];
  xKey: string;
  yKey: string;
  label: string;
  referenceValue?: number;
  referenceLabel?: string;
  height?: number;
  unit?: string;
}) {
  const { series, tones } = usePalette();
  return (
    <ChartFrame height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={series[0]} stopOpacity={0.3} />
            <stop offset="100%" stopColor={series[0]} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.15} vertical={false} />
        <XAxis dataKey={xKey} {...axisProps} />
        <YAxis domain={[0, 100]} {...axisProps} />
        <Tooltip content={<ChartTooltip unit={unit} />} />
        {referenceValue !== undefined && (
          <ReferenceLine
            y={referenceValue}
            stroke={tones.warning}
            strokeDasharray="4 4"
            label={{
              value: referenceLabel ?? `${referenceValue}%`,
              position: 'right',
              fontSize: 10,
              fill: tones.warning,
            }}
          />
        )}
        <Area
          type="monotone"
          dataKey={yKey}
          name={label}
          stroke={series[0]}
          strokeWidth={2.5}
          fill="url(#trendFill)"
        />
      </AreaChart>
    </ChartFrame>
  );
}

export function CategoryBarChart({
  data,
  xKey,
  yKey,
  label,
  height = 260,
  colorByStatus,
  referenceValue,
  unit = '%',
  domain,
}: {
  data: Record<string, any>[];
  xKey: string;
  yKey: string;
  label: string;
  height?: number;
  colorByStatus?: boolean;
  referenceValue?: number;
  unit?: string;
  domain?: [number, number];
}) {
  const { series, tones } = usePalette();
  return (
    <ChartFrame height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.15} vertical={false} />
        <XAxis dataKey={xKey} {...axisProps} interval={0} angle={-15} textAnchor="end" height={48} />
        <YAxis domain={domain ?? [0, 100]} {...axisProps} />
        <Tooltip content={<ChartTooltip unit={unit} />} cursor={{ fill: 'currentColor', opacity: 0.06 }} />
        {referenceValue !== undefined && (
          <ReferenceLine y={referenceValue} stroke={tones.warning} strokeDasharray="4 4" />
        )}
        <Bar dataKey={yKey} name={label} radius={[4, 4, 0, 0]}>
          {data.map((entry, index) => (
            <Cell
              key={index}
              fill={
                colorByStatus
                  ? (tones[entry.status as string] ?? series[0])
                  : series[index % series.length]
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ChartFrame>
  );
}

export function DonutChart({
  data,
  nameKey,
  valueKey,
  height = 240,
  colors,
}: {
  data: Record<string, any>[];
  nameKey: string;
  valueKey: string;
  height?: number;
  colors?: string[];
}) {
  const { series } = usePalette();
  const palette = colors ?? series;

  // A zero-value slice combined with paddingAngle makes Recharts produce empty
  // sectors for the *whole* pie, so drop empty categories before rendering.
  // The index into `palette` stays tied to the original row so a category keeps
  // its colour whether or not its neighbours are present.
  const slices = data
    .map((entry, index) => ({ entry, index }))
    .filter(({ entry }) => Number(entry[valueKey]) > 0);

  if (slices.length === 0) {
    return (
      <div
        style={{ height }}
        className="flex items-center justify-center text-sm text-muted-foreground"
      >
        No data to plot yet.
      </div>
    );
  }

  return (
    <ChartFrame height={height}>
      <PieChart>
        <Tooltip content={<ChartTooltip unit="" />} />
        <Legend
          verticalAlign="bottom"
          height={32}
          iconType="circle"
          formatter={(value) => <span className="text-xs text-muted-foreground">{value}</span>}
        />
        <Pie
          data={slices.map(({ entry }) => entry)}
          dataKey={valueKey}
          nameKey={nameKey}
          innerRadius="55%"
          outerRadius="80%"
          paddingAngle={slices.length > 1 ? 2 : 0}
          // Recharts 2.x pie mount-animation does not complete under React 19,
          // leaving empty sector groups. The chart is static data anyway.
          isAnimationActive={false}
        >
          {slices.map(({ index }) => (
            <Cell key={index} fill={palette[index % palette.length]} />
          ))}
        </Pie>
      </PieChart>
    </ChartFrame>
  );
}

export function MultiLineChart({
  data,
  xKey,
  series,
  height = 260,
  unit = '',
}: {
  data: Record<string, any>[];
  xKey: string;
  series: { key: string; label: string }[];
  height?: number;
  unit?: string;
}) {
  const { series: palette } = usePalette();
  return (
    <ChartFrame height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.15} vertical={false} />
        <XAxis dataKey={xKey} {...axisProps} />
        <YAxis {...axisProps} />
        <Tooltip content={<ChartTooltip unit={unit} />} />
        <Legend
          iconType="circle"
          formatter={(value) => <span className="text-xs text-muted-foreground">{value}</span>}
        />
        {series.map((entry, index) => (
          <Line
            key={entry.key}
            type="monotone"
            dataKey={entry.key}
            name={entry.label}
            stroke={palette[index % palette.length]}
            strokeWidth={2}
            dot={false}
          />
        ))}
      </LineChart>
    </ChartFrame>
  );
}

export function CorrelationScatter({
  points,
  height = 320,
}: {
  points: { attendance: number; performance: number; label: string }[];
  height?: number;
}) {
  const { series } = usePalette();
  return (
    <ChartFrame height={height}>
      <ScatterChart margin={{ top: 12, right: 16, bottom: 12, left: -12 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.15} />
        <XAxis
          type="number"
          dataKey="attendance"
          name="Attendance"
          domain={[0, 100]}
          unit="%"
          {...axisProps}
          label={{
            value: 'Attendance %',
            position: 'insideBottom',
            offset: -4,
            fontSize: 11,
            fill: 'currentColor',
          }}
        />
        <YAxis
          type="number"
          dataKey="performance"
          name="Performance"
          domain={[0, 100]}
          unit="%"
          {...axisProps}
        />
        <ZAxis range={[45, 45]} />
        <Tooltip content={<ChartTooltip unit="%" />} cursor={{ strokeDasharray: '3 3' }} />
        <Scatter data={points} fill={series[0]} fillOpacity={0.7} />
      </ScatterChart>
    </ChartFrame>
  );
}
