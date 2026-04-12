'use client';

import React from 'react';
import MuiTable from '@mui/material/Table';
import TableContainer from '@mui/material/TableContainer';
import MuiTableHead from '@mui/material/TableHead';
import MuiTableBody from '@mui/material/TableBody';
import MuiTableRow from '@mui/material/TableRow';
import MuiTableCell from '@mui/material/TableCell';
import MuiTableFooter from '@mui/material/TableFooter';
import { styled } from '@mui/material/styles';

const StyledTable = styled(MuiTable)(({ theme }) => ({
  '& thead': {
    '& tr': {
      borderBottom: `1px solid ${theme.palette.divider}`,
    },
  },
}));

const StyledTableRow = styled(MuiTableRow)(({ theme }) => ({
  '&:hover': {
    backgroundColor: theme.palette.action.hover,
  },
  '&:last-child td, &:last-child th': {
    border: 0,
  },
}));

const StyledTableCell = styled(MuiTableCell)(({ theme }) => ({
  padding: theme.spacing(1),
}));

const StyledTableHead = styled(MuiTableCell)(({ theme }) => ({
  fontWeight: 600,
  backgroundColor: theme.palette.background.paper,
  color: theme.palette.text.primary,
}));

export const Table = React.forwardRef<HTMLTableElement, React.ComponentProps<typeof MuiTable>>(
  (props, ref) => (
    <TableContainer>
      <StyledTable ref={ref} {...props} />
    </TableContainer>
  )
);
Table.displayName = 'Table';

export const TableHeader = React.forwardRef<HTMLTableSectionElement, React.ComponentProps<typeof MuiTableHead>>(
  (props, ref) => <MuiTableHead ref={ref} {...props} />
);
TableHeader.displayName = 'TableHeader';

export const TableBody = React.forwardRef<HTMLTableSectionElement, React.ComponentProps<typeof MuiTableBody>>(
  (props, ref) => <MuiTableBody ref={ref} {...props} />
);
TableBody.displayName = 'TableBody';

export const TableFooter = React.forwardRef<HTMLTableSectionElement, React.ComponentProps<typeof MuiTableFooter>>(
  (props, ref) => <MuiTableFooter ref={ref} {...props} />
);
TableFooter.displayName = 'TableFooter';

export const TableRow = React.forwardRef<HTMLTableRowElement, React.ComponentProps<typeof MuiTableRow>>(
  (props, ref) => <StyledTableRow ref={ref} {...props} />
);
TableRow.displayName = 'TableRow';

export const TableHead = React.forwardRef<HTMLTableCellElement, React.ComponentProps<typeof MuiTableCell>>(
  (props, ref) => <StyledTableHead ref={ref} variant="head" {...props} />
);
TableHead.displayName = 'TableHead';

export const TableCell = React.forwardRef<HTMLTableCellElement, React.ComponentProps<typeof MuiTableCell>>(
  (props, ref) => <StyledTableCell ref={ref} {...props} />
);
TableCell.displayName = 'TableCell';

export const TableCaption = React.forwardRef<HTMLTableCaptionElement, React.ComponentProps<'caption'>>(
  (props, ref) => <caption ref={ref} style={{ marginTop: 16, fontSize: '0.875rem', color: 'rgba(0, 0, 0, 0.6)' }} {...props} />
);
TableCaption.displayName = 'TableCaption';
