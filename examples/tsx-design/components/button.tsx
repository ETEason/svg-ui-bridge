import React from 'react';

export type ButtonState = 'default' | 'disabled';

export function Button({ id, x, label, state }: {
  id: string; x: number; label: string; state: ButtonState;
}) {
  return <g id={id} data-component="Button" data-layout="row center"
    data-note={`Static ${state} appearance; enable when the form is dirty`}>
    <rect x={x} y="104" width="144" height="40" rx="8"
      fill={`var(--color-${state === 'disabled' ? 'muted' : 'primary'})`} />
    <text x={x + 72} y="129" textAnchor="middle" fontSize="15"
      fill="var(--color-text)">{label}</text>
  </g>;
}
