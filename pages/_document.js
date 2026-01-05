import { Html, Head, Main, NextScript } from 'next/document'

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <meta name="theme-color" content="#667eea" />
        <meta
          name="description"
          content="ML-powered offline Gold (XAUUSD) price prediction system. Real-time XGBoost forecasts with technical indicators."
        />
        <meta name="keywords" content="gold, xauusd, prediction, ml, xgboost, trading" />
        
        {/* Open Graph / Social Media */}
        <meta property="og:type" content="website" />
        <meta property="og:title" content="Gold Price Prediction" />
        <meta
          property="og:description"
          content="Machine learning powered XAUUSD price prediction"
        />
        
        {/* Favicon */}
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='75' font-size='75'>🥇</text></svg>" />
        
        {/* Preload fonts */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  )
}
