# CV Match V3 — UI/UX Refresh

גרסה מעוצבת ומלוטשת יותר של CV Match, תוך שמירה על הפונקציונליות של V2.

## מה חדש ב-V3
- שפה גרפית מלאה: Navy / Gold / White, עם כרטיסים, גרדיאנטים ואלמנטים גרפיים מובנים.
- Hero חדש שמסביר מיד מה האפליקציה עושה.
- 3 דרכי הכנסת משרה מוצגות ככרטיסים ברורים: צילום מסך, לינק, תיאור חופשי.
- עיצוב מחודש למסך הפרופיל המקצועי, שלמות פרופיל, תמונה קבועה וכרטיסי ניסיון.
- עיצוב מחודש ל-Smart Import: העלאת CV ישן / כתיבה חופשית / שאלון.
- עיצוב רספונסיבי משופר למובייל ולדסקטופ.
- עיצוב CV Preview משופר ושמירה על A4 להדפסה/PDF.

## העלאה ל-GitHub / Vercel
החלף את תוכן ה-repository הקיים בתוכן התיקייה הזו, תוך שמירה על מבנה התיקיות:

```
app.py
requirements.txt
vercel.json
templates/
  index.html
static/
  style.css
  app.js
data/
  profile_photo_example.jpg
  profile_photo_meta.json
```

אחרי Commit ל-main, Vercel אמור לבצע Redeploy אוטומטי.

## OpenAI
כדי שהייבוא החכם וההתאמה האוטומטית יעבדו, יש להוסיף ב-Vercel Environment Variable בשם:

`OPENAI_API_KEY`

אין לשים את המפתח בקוד או ב-GitHub.
