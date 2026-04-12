import React from 'react';
import MuiButton, { ButtonProps as MuiButtonProps } from '@mui/material/Button';

export interface ButtonProps extends Omit<MuiButtonProps, 'variant' | 'size'> {
  variant?: 'default' | 'outline' | 'secondary' | 'ghost' | 'destructive' | 'link' | 'contained' | 'outlined' | 'text';
  size?: 'xs' | 'sm' | 'default' | 'lg' | 'icon' | 'small' | 'medium' | 'large';
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'default', size = 'default', asChild = false, children, ...props }, ref) => {
    const getMuiVariant = (v: ButtonProps['variant']) => {
      switch (v) {
        case 'default':
          return 'contained';
        case 'outline':
          return 'outlined';
        case 'secondary':
          return 'outlined';
        case 'ghost':
          return 'text';
        case 'destructive':
          return 'contained';
        case 'link':
          return 'text';
        default:
          return v;
      }
    };

    const getColor = (v: ButtonProps['variant']) => {
      switch (v) {
        case 'destructive':
          return 'error';
        case 'default':
          return 'primary';
        case 'secondary':
          return 'secondary';
        default:
          return 'primary';
      }
    };

    const getMuiSize = (s: ButtonProps['size']) => {
      switch (s) {
        case 'xs':
        case 'sm':
          return 'small';
        case 'default':
          return 'medium';
        case 'lg':
          return 'large';
        case 'icon':
          return 'medium';
        default:
          return 'medium';
      }
    };

    // If asChild is true, render the first child as the button element
    if (asChild && React.isValidElement(children)) {
      const childElement = children as React.ReactElement<any>;
      return React.cloneElement(childElement, {
        ref,
        className: `${props.className || ''} ${childElement.props?.className || ''}`,
        ...(props as any),
      });
    }

    return (
      <MuiButton
        ref={ref}
        variant={getMuiVariant(variant)}
        color={getColor(variant)}
        size={getMuiSize(size)}
        {...props}
      >
        {children}
      </MuiButton>
    );
  }
);

Button.displayName = 'Button';
