'use client';

import React from 'react';
import MuiDialog from '@mui/material/Dialog';
import MuiDialogTitle from '@mui/material/DialogTitle';
import MuiDialogContent from '@mui/material/DialogContent';
import MuiDialogActions from '@mui/material/DialogActions';
import MuiDialogContentText from '@mui/material/DialogContentText';
import IconButton from '@mui/material/IconButton';
import CloseIcon from '@mui/icons-material/Close';

interface DialogContextType {
  open: boolean;
  setOpen: (open: boolean) => void;
}

const DialogContext = React.createContext<DialogContextType | null>(null);

export const Dialog = ({ open, onOpenChange, children }: any) => {
  const [isOpen, setIsOpen] = React.useState(open || false);

  React.useEffect(() => {
    if (open !== undefined) setIsOpen(open);
  }, [open]);

  const handleOpenChange = (newOpen: boolean) => {
    setIsOpen(newOpen);
    onOpenChange?.(newOpen);
  };

  return (
    <DialogContext.Provider value={{ open: isOpen, setOpen: handleOpenChange }}>
      {children}
    </DialogContext.Provider>
  );
};

export const DialogTrigger = React.forwardRef<any, any>(({ children, asChild, ...props }, ref) => {
  const context = React.useContext(DialogContext);
  if (!context) return null;

  return (
    <div
      ref={ref}
      onClick={() => context.setOpen(true)}
      {...props}
    >
      {children}
    </div>
  );
});
DialogTrigger.displayName = 'DialogTrigger';

export const DialogPortal = ({ children }: any) => <>{children}</>;

export const DialogClose = React.forwardRef<HTMLButtonElement, any>(({ children, ...props }, ref) => {
  const context = React.useContext(DialogContext);
  if (!context) return null;

  return (
    <button
      ref={ref}
      onClick={() => context.setOpen(false)}
      {...props}
    >
      {children}
    </button>
  );
});
DialogClose.displayName = 'DialogClose';

export const DialogOverlay = React.forwardRef<HTMLDivElement, any>((props, ref) => (
  <div ref={ref} {...props} />
));
DialogOverlay.displayName = 'DialogOverlay';

export const DialogContent = React.forwardRef<HTMLDivElement, any>(
  ({ children, showCloseButton = true, ...props }, ref) => {
    const context = React.useContext(DialogContext);
    if (!context) return null;

    return (
      <MuiDialog
        ref={ref}
        open={context.open}
        onClose={() => context.setOpen(false)}
        {...props}
      >
        {showCloseButton && (
          <IconButton
            aria-label="close"
            onClick={() => context.setOpen(false)}
            sx={{
              position: 'absolute',
              right: 8,
              top: 8,
              color: 'grey.500',
            }}
          >
            <CloseIcon />
          </IconButton>
        )}
        {children}
      </MuiDialog>
    );
  }
);
DialogContent.displayName = 'DialogContent';

export const DialogHeader = React.forwardRef<HTMLDivElement, React.ComponentProps<'div'>>(
  (props, ref) => <div ref={ref} {...props} />
);
DialogHeader.displayName = 'DialogHeader';

export const DialogFooter = React.forwardRef<HTMLDivElement, React.ComponentProps<'div'>>(
  (props, ref) => <div ref={ref} {...props} />
);
DialogFooter.displayName = 'DialogFooter';

export const DialogTitle = React.forwardRef<HTMLDivElement, any>(
  (props, ref) => <MuiDialogTitle ref={ref} {...props} />
);
DialogTitle.displayName = 'DialogTitle';

export const DialogDescription = React.forwardRef<HTMLDivElement, any>(
  (props, ref) => <MuiDialogContentText ref={ref as any} {...props} />
);
DialogDescription.displayName = 'DialogDescription';
