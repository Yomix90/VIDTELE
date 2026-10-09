import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:vidtele_mobile/main.dart';

void main() {
  testWidgets('VidTele app initializes smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(
      const ProviderScope(
        child: VidTeleApp(),
      ),
    );

    // Verify that the splash or brand title exists
    expect(find.text('VIDTELE'), findsOneWidget);
  });
}
