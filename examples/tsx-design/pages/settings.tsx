import React from 'react';
import { Button, type ButtonState } from '../components/button';
import { theme } from '../theme';

export function Settings({ state }: { state: ButtonState }) {
  return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 168"
    width="360" height="168" data-screen="Settings" data-target="desktop-360">
    <style>{theme}</style>
    <g id="SettingsPanel" data-component="Panel" data-layout="absolute">
      <rect width="360" height="168" fill="var(--color-bg)" />
      <text x="24" y="48" fontSize="24" fill="var(--color-text)">Settings</text>
      {[
        { id: 'SaveButton', label: 'Save', x: 24 },
        { id: 'ResetButton', label: 'Reset', x: 192 },
      ].map(button => <Button key={button.id} {...button} state={state} />)}
    </g>
  </svg>;
}
