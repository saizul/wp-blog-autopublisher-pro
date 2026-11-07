---
title: "How I Fix Core Web Vitals on WordPress Without Piling On Plugins"
slug: fix-core-web-vitals-wordpress
excerpt: "A practical, measured approach to LCP, CLS and INP on WordPress sites."
categories: [WordPress, Performance]
tags: [core web vitals, lcp, page speed]
seo_title: "Fix Core Web Vitals on WordPress (Practical Guide)"
meta_description: "Step-by-step approach to improving LCP, CLS and INP on WordPress using measurement first and fewer plugins."
focus_keyword: core web vitals wordpress
featured_image: auto
---

## Start with measurement

Before changing anything, record field data (CrUX or Search Console) and a lab baseline. Note the date, the tool and the template you tested.

## Largest Contentful Paint

1. Serve the hero image in a modern format at the right size.
2. Preload the LCP image and avoid lazy-loading it.
3. Cut render-blocking CSS from plugins you do not use on that template.

## Layout shift and interaction

- Set width and height on images and embeds.
- Defer non-critical scripts and re-test INP on a real mid-range phone.

> Write down what you changed and the before/after numbers. That record is your proof of experience.
