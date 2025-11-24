// GA4 helper utilities

export const GA_MEASUREMENT_ID = "G-XXXXXXXXXX"; 

export const trackEvent = ({ action, category, label, value }) => {
  if (typeof window === "undefined") return;
  if (!window.gtag) return;

  window.gtag("event", action, {
    event_category: category,
    event_label: label,
    value
  });
};

export const trackPageView = (path) => {
  if (typeof window === "undefined") return;
  if (!window.gtag) return;

  window.gtag("event", "page_view", {
    page_path: path
  });
};
