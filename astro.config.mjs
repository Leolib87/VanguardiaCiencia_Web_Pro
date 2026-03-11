// @ts-check

import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
	site: 'https://vanguardia-ciencia-web-pro.vercel.app',
	integrations: [mdx(), sitemap()],
	image: {
		remotePatterns: [
			{
				protocol: 'https',
				hostname: 'upload.wikimedia.org',
			},
		],
	},
  server: {
    port: 4321
  }
});
