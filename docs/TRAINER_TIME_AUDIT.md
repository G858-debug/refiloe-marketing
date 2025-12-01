# Trainer Time Audit Calculator

A mobile-first lead generation tool that helps trainers discover how much time and money they're losing to admin tasks.

## Overview

The Trainer Time Audit Calculator is a 3-step interactive tool that:
1. Collects information about trainers' time spent on admin tasks
2. Calculates and visualizes the time and revenue impact
3. Captures leads (name + WhatsApp) in exchange for a personalized report

## Features

### Step 1: Input Form
- Active client count (1-100)
- Time spent on various admin tasks (0-10 hours per week):
  - Scheduling/bookings
  - Chasing payments
  - Writing programs
  - Client messages
  - Admin/paperwork
- Hourly rate (in Rands)

### Step 2: Results Display
- Total hours lost per week
- Revenue impact (weekly, monthly, yearly)
- Visual breakdown of time allocation
- Personalized tip based on biggest time sink
- Social sharing functionality

### Step 3: Lead Capture
- Name input
- WhatsApp number with country code selector
- Opt-in for personalized report
- Success confirmation

## Technical Implementation

### Frontend
- **Location**: `/templates/trainer_time_audit.html`
- **Technology**: React (via CDN) + Tailwind CSS
- **State Management**: React hooks (useState)
- **Responsive**: Mobile-first design

### Backend
- **Route**: `/trainer-time-audit` - Serves the HTML page
- **API Endpoint**: `/api/trainer-audit/submit` - POST endpoint for form submission
- **API Endpoint**: `/api/trainer-audit/list` - GET endpoint to retrieve submissions

### Database
- **Migration**: `/migrations/004_trainer_audits.sql`
- **Table**: `trainer_audits`
- **Fields**:
  - Lead info: name, country_code, phone
  - Business metrics: active_clients, hourly_rate
  - Time breakdown: scheduling_hours, payment_hours, program_hours, message_hours, admin_hours
  - Calculated values: total_hours, weekly_lost, monthly_lost, yearly_lost, biggest_time_sink
  - Metadata: id, created_at, updated_at

## Usage

### Accessing the Tool
Navigate to: `https://your-domain.com/trainer-time-audit`

### Viewing Submissions
GET request to: `https://your-domain.com/api/trainer-audit/list?limit=50`

Response:
```json
{
  "success": true,
  "count": 10,
  "audits": [
    {
      "id": "uuid",
      "name": "John Doe",
      "phone": "821234567",
      "country_code": "+27",
      "active_clients": 15,
      "total_hours": 17.5,
      "monthly_lost": 35000,
      "yearly_lost": 455000,
      "biggest_time_sink": "Client Messages",
      "created_at": "2025-12-01T10:00:00Z"
    }
  ]
}
```

## Database Setup

Run the migration to create the required table:

```bash
# If using Supabase CLI
supabase db push

# Or manually run the SQL file
psql -f migrations/004_trainer_audits.sql
```

## Future Enhancements

### Planned Features
- [ ] WhatsApp integration for automated report delivery
- [ ] PDF report generation with personalized insights
- [ ] Email follow-up sequences
- [ ] Analytics dashboard for viewing conversion metrics
- [ ] A/B testing different copy variations
- [ ] Integration with CRM

### WhatsApp Report Integration
To enable automated WhatsApp report delivery, update the `submit_trainer_audit()` function in `app.py`:

```python
# Uncomment these lines in the submit_trainer_audit function
whatsapp_notifier = get_whatsapp_notifier()
if whatsapp_notifier:
    whatsapp_notifier.send_trainer_audit_report(audit_data)
```

Then create the `send_trainer_audit_report()` method in the WhatsAppNotifier class.

## Design System

### Colors
- **Primary**: Deep Purple (#6B46C1)
- **Secondary**: Violet (#7C3AED)
- **Accent**: Gold (#F59E0B)
- **Background**: Purple/Violet gradient

### Typography
- **Font**: Inter (Google Fonts)
- **Weights**: 300-800

### Components
- Gradient buttons with hover effects
- Smooth step transitions
- Interactive sliders with live feedback
- Responsive card layout
- Progress indicators

## Marketing Strategy

### Value Proposition
The tool provides immediate value without mentioning Refiloe as a product:
- Helps trainers identify inefficiencies
- Quantifies the cost of poor systems
- Creates awareness of the problem
- Builds trust through free value

### Lead Nurture
After capturing leads, you can:
1. Send WhatsApp report with actionable tips
2. Follow up with case studies
3. Invite to webinar or demo
4. Introduce Refiloe as the solution

### Share Functionality
Built-in social sharing encourages viral growth:
- Mobile-optimized share API
- Pre-populated share text
- Clipboard fallback for unsupported browsers

## Analytics to Track

- Completion rate by step
- Average time on each step
- Most common time sinks
- Average revenue lost (for positioning)
- Share button click rate
- Form submission success rate

## Support

For questions or issues, contact the development team or check the main README.
