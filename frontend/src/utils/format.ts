/**
 * Format a number as a currency string (USD with European decimal format).
 * Example: 1234.56 -> "$1.234,56"
 */
export const formatCurrency = (amount: number | string | undefined | null): string => {
    if (amount === undefined || amount === null) {
        return '$0,00';
    }

    const numericAmount = typeof amount === 'string' ? parseFloat(amount) : amount;

    if (isNaN(numericAmount)) {
        return '$0,00';
    }

    // Use European format (de-DE) which uses comma for decimals and dot for thousands
    const formatted = new Intl.NumberFormat('de-DE', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(numericAmount);

    return `$${formatted}`;
};

/**
 * Format a number with commas.
 * Example: 1234 -> "1,234"
 */
export const formatNumber = (amount: number | string | undefined | null): string => {
    if (amount === undefined || amount === null) {
        return '0';
    }

    const numericAmount = typeof amount === 'string' ? parseFloat(amount) : amount;

    if (isNaN(numericAmount)) {
        return '0';
    }

    return new Intl.NumberFormat('en-US').format(numericAmount);
};
