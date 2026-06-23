const egyptLocale = "en-EG";

export const egpFormatter = new Intl.NumberFormat(egyptLocale, {
  style: "currency",
  currency: "EGP",
  maximumFractionDigits: 2
});

export const dateTimeFormatter = new Intl.DateTimeFormat(egyptLocale, {
  dateStyle: "medium",
  timeStyle: "short"
});

export function formatEgp(value: number) {
  return egpFormatter.format(value);
}

export function formatDateTime(value: string | Date) {
  return dateTimeFormatter.format(typeof value === "string" ? new Date(value) : value);
}
