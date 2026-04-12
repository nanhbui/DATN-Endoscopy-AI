import React from 'react';
import MuiChip from '@mui/material/Chip';

export interface BadgeProps {
  variant?: 'default' | 'secondary' | 'destructive' | 'outline' | 'ghost' | 'link';
  children?: React.ReactNode;
  label?: React.ReactNode;
  [key: string]: any;
}

export const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  ({ variant = 'default', children, label, ...props }, ref) => {
    const getMuiVariant = (v: BadgeProps['variant']) => {
      switch (v) {
        case 'default':
          return 'filled' as const;
        case 'outline':
          return 'outlined' as const;
        default:
          return 'filled' as const;
      }
    };

    const getColor = (v: BadgeProps['variant']) => {
      switch (v) {
        case 'destructive':
          return 'error' as const;
        default:
          return 'primary' as const;
      }
    };

    return (
      <MuiChip
        ref={ref}
        variant={getMuiVariant(variant)}
        color={getColor(variant)}
        size="small"
        label={label || children}
        {...props}
      />
    );
  }
);

Badge.displayName = 'Badge';
