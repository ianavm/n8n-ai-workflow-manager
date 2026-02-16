"""
Google Slides report creator.

Creates professional n8n workflow performance presentations
using Google Slides API. Includes charts, key insights,
and optimization recommendations.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth import get_google_credentials


class SlidesCreator:
    """Creates Google Slides presentations for n8n workflow performance."""

    def __init__(self, credentials):
        """
        Initialize slides creator.

        Args:
            credentials: Authenticated Google API credentials
        """
        self.creds = credentials
        self.slides_service = build('slides', 'v1', credentials=credentials)
        self.drive_service = build('drive', 'v3', credentials=credentials)
        self.presentation_id = None
        self.slides = []

    def create_presentation(self, title: str) -> str:
        """
        Create a new Google Slides presentation.

        Args:
            title: Presentation title

        Returns:
            Presentation ID
        """
        presentation = {'title': title}

        presentation = self.slides_service.presentations().create(
            body=presentation
        ).execute()

        self.presentation_id = presentation.get('presentationId')
        print(f"  Created presentation: {title}")
        print(f"  ID: {self.presentation_id}")

        return self.presentation_id

    def build_full_presentation(self, analysis_data: Dict[str, Any],
                                charts_dir: str,
                                title: str = "n8n Workflow Performance Report") -> str:
        """
        Build complete performance report presentation.

        Args:
            analysis_data: Analysis results dictionary
            charts_dir: Directory containing chart PNG files
            title: Presentation title

        Returns:
            Presentation URL
        """
        self.create_presentation(title)

        presentation = self.slides_service.presentations().get(
            presentationId=self.presentation_id
        ).execute()

        self.slides = presentation.get('slides', [])

        print("\nBuilding slides...")
        requests = []

        # Slide 1: Title slide
        requests.extend(self._build_title_slide(
            self.slides[0]['objectId'], title,
            datetime.now().strftime("%B %d, %Y")
        ))

        # Slide 2: Executive Summary
        requests.extend(self._build_summary_slide(analysis_data))

        # Slide 3: Success Rates
        requests.extend(self._build_chart_slide(
            "Workflow Success Rates",
            Path(charts_dir) / "workflow_success_rates.png"
        ))

        # Slide 4: Execution Volume
        requests.extend(self._build_chart_slide(
            "Execution Volume by Workflow",
            Path(charts_dir) / "category_performance.png"
        ))

        # Slide 5: Throughput
        requests.extend(self._build_chart_slide(
            "Workflow Throughput Comparison",
            Path(charts_dir) / "workflow_comparison.png"
        ))

        # Slide 6: Execution Trends
        requests.extend(self._build_chart_slide(
            "Execution Trends Over Time",
            Path(charts_dir) / "execution_trend.png"
        ))

        # Slide 7: Recommendations
        requests.extend(self._build_recommendations_slide(analysis_data))

        if requests:
            self.slides_service.presentations().batchUpdate(
                presentationId=self.presentation_id,
                body={'requests': requests}
            ).execute()
            print("  All slides created")

        self._insert_all_charts(charts_dir)
        self._set_sharing_permissions()

        url = f"https://docs.google.com/presentation/d/{self.presentation_id}/edit"
        print(f"\n  Presentation complete!")
        print(f"  URL: {url}")

        return url

    def _build_title_slide(self, slide_id: str, title: str, date: str) -> List[Dict]:
        """Build title slide requests."""
        return [
            {'deleteText': {'objectId': slide_id, 'textRange': {'type': 'ALL'}}},
            {'insertText': {'objectId': slide_id, 'text': f"{title}\n\n{date}", 'insertionIndex': 0}}
        ]

    def _build_summary_slide(self, analysis_data: Dict[str, Any]) -> List[Dict]:
        """Build executive summary slide."""
        summary = analysis_data.get('summary', {})

        summary_text = f"""Executive Summary

Total Workflows: {summary.get('total_workflows', 0)}
Total Executions: {summary.get('total_executions', 0):,}
Overall Success Rate: {summary.get('overall_success_rate', 0):.1f}%
Average Duration: {summary.get('avg_duration_seconds', 0):.1f}s

Key Insights:
"""
        recommendations = analysis_data.get('recommendations', [])
        for rec in recommendations[:3]:
            summary_text += f"- {rec}\n"

        return [{'createSlide': {'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'}}}]

    def _build_chart_slide(self, title: str, chart_path: Path) -> List[Dict]:
        """Build slide with chart image."""
        return [{'createSlide': {'slideLayoutReference': {'predefinedLayout': 'TITLE_ONLY'}}}]

    def _build_recommendations_slide(self, analysis_data: Dict[str, Any]) -> List[Dict]:
        """Build recommendations slide."""
        recommendations = analysis_data.get('recommendations', [])
        rec_text = "Optimization Recommendations\n\n"
        for i, rec in enumerate(recommendations, 1):
            rec_text += f"{i}. {rec}\n\n"

        return [{'createSlide': {'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'}}}]

    def _insert_all_charts(self, charts_dir: str):
        """Upload and insert all chart images into slides."""
        charts_path = Path(charts_dir)
        chart_files = {
            'workflow_success_rates.png': 2,
            'category_performance.png': 3,
            'workflow_comparison.png': 4,
            'execution_trend.png': 5
        }

        for chart_file, slide_index in chart_files.items():
            chart_path = charts_path / chart_file
            if chart_path.exists():
                self._insert_image_on_slide(chart_path, slide_index)
            else:
                print(f"  Chart not found: {chart_file}")

    def _insert_image_on_slide(self, image_path: Path, slide_index: int):
        """Upload image to Drive and insert into slide."""
        try:
            file_metadata = {'name': image_path.name, 'mimeType': 'image/png'}

            media = self.drive_service.files().create(
                body=file_metadata, media_body=str(image_path), fields='id,webContentLink'
            ).execute()

            image_url = f"https://drive.google.com/uc?id={media.get('id')}"

            presentation = self.slides_service.presentations().get(
                presentationId=self.presentation_id
            ).execute()

            slides = presentation.get('slides', [])
            if slide_index >= len(slides):
                return

            slide_id = slides[slide_index]['objectId']

            requests = [{
                'createImage': {
                    'url': image_url,
                    'elementProperties': {
                        'pageObjectId': slide_id,
                        'size': {'width': {'magnitude': 600, 'unit': 'PT'}, 'height': {'magnitude': 350, 'unit': 'PT'}},
                        'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': 50, 'translateY': 100, 'unit': 'PT'}
                    }
                }
            }]

            self.slides_service.presentations().batchUpdate(
                presentationId=self.presentation_id, body={'requests': requests}
            ).execute()

            print(f"  Inserted chart: {image_path.name}")

        except Exception as e:
            print(f"  Failed to insert {image_path.name}: {e}")

    def _set_sharing_permissions(self):
        """Set presentation to viewable by anyone with link."""
        try:
            self.drive_service.permissions().create(
                fileId=self.presentation_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
            print("  Sharing enabled (anyone with link can view)")
        except Exception as e:
            print(f"  Warning: Could not set sharing permissions: {e}")


def main():
    """Main function for command-line usage."""
    from config_loader import load_config

    try:
        config = load_config()

        print("Authenticating with Google...")
        creds = get_google_credentials(
            credentials_path=config['google_oauth']['credentials_path'],
            token_path=config['google_oauth']['token_path']
        )

        tmp_dir = Path(config['paths']['tmp_dir'])
        analysis_file = tmp_dir / "analysis_results.json"
        charts_dir = config['paths']['charts_dir']

        if not analysis_file.exists():
            print("Error: analysis_results.json not found.")
            print("Please run tools/workflow_analyzer.py first.")
            sys.exit(1)

        with open(analysis_file, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)

        title = config['reporting'].get('title', 'n8n Workflow Performance Report')
        title = f"{title} - {datetime.now().strftime('%B %Y')}"

        creator = SlidesCreator(creds)
        presentation_url = creator.build_full_presentation(
            analysis_data=analysis_data, charts_dir=charts_dir, title=title
        )

        output_data = {
            'presentation_id': creator.presentation_id,
            'presentation_url': presentation_url,
            'created_at': datetime.now().isoformat()
        }

        output_file = tmp_dir / "presentation_info.json"
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"\n  Presentation info saved to: {output_file}")

    except HttpError as e:
        print(f"\nGoogle API Error: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
