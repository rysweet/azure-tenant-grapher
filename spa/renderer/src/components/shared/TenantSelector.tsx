import React from 'react';
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormHelperText,
  SelectChangeEvent,
} from '@mui/material';

interface TenantSelectorProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  required?: boolean;
  helperText?: string;
}

/**
 * TenantSelector - Reusable tenant selection dropdown component
 *
 * Provides a dropdown selector for Azure tenant IDs with predefined options
 * for common tenants (DefenderATEVET17, SimServAutomation, Simuland).
 */
const TenantSelector: React.FC<TenantSelectorProps> = ({
  label,
  value,
  onChange,
  disabled = false,
  required = false,
  helperText,
}) => {
  const handleChange = (event: SelectChangeEvent<string>) => {
    onChange(event.target.value);
  };

  return (
    <FormControl fullWidth required={required} disabled={disabled}>
      <InputLabel>{label}</InputLabel>
      <Select
        value={value}
        label={label}
        onChange={handleChange}
      >
        <MenuItem value="">
          <em>None</em>
        </MenuItem>
        <MenuItem value="3cd87a41-1f61-4aef-a212-cefdecd9a2d1">
          DefenderATEVET17 (Tenant 1)
        </MenuItem>
        <MenuItem value="8d788dbd-cd1c-4e00-b371-3933a12c0f7d">
          SimServAutomation (Tenant 2)
        </MenuItem>
        <MenuItem value="506f82b2-e2e7-40a2-b0be-ea6f8cb908f8">
          Simuland (Tenant 3)
        </MenuItem>
      </Select>
      {helperText && <FormHelperText>{helperText}</FormHelperText>}
    </FormControl>
  );
};

export default TenantSelector;
