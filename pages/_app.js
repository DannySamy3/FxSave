import React from "react";

/**
 * Next.js App Component
 *
 * This is the root component for all pages.
 * Initializes global styles and metadata.
 */

function MyApp({ Component, pageProps }) {
  return (
    <>
      <style global jsx>{`
        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }

        html,
        body {
          width: 100%;
          height: 100%;
          overflow-x: hidden;
        }

        body {
          background: #ffffff;
          color: #1f2937;
          line-height: 1.6;
        }

        /* Scrollbar styling */
        ::-webkit-scrollbar {
          width: 8px;
        }

        ::-webkit-scrollbar-track {
          background: #f3f4f6;
        }

        ::-webkit-scrollbar-thumb {
          background: #d1d5db;
          border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
          background: #9ca3af;
        }

        /* Selection styling */
        ::selection {
          background: #667eea;
          color: white;
        }

        ::-moz-selection {
          background: #667eea;
          color: white;
        }
      `}</style>
      <Component {...pageProps} />
    </>
  );
}

export default MyApp;
