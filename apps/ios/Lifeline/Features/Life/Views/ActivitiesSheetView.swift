import SwiftUI

/// Activities: gym, holidays, courses and more. Opens as a sheet from the Life screen (ADR 0009).
struct ActivitiesSheetView: View {
    let state: ActivitiesViewState
    var actions: ActionTabActions = .noop

    var body: some View {
        SheetContainer(title: "Activities", closeIdentifier: "activities.done", onClose: actions.onClose) {
            RowGroupTitle(text: L10n.tr("What you can do"))
            ActionList(actions: state.actions, isBusy: state.isBusy, onAction: actions.onAction, emptyText: L10n.tr("Nothing to do here this year."))
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("List · light") {
    ActivitiesSheetView(state: Fixtures.Activities.list)
}

#Preview("List · dark") {
    ActivitiesSheetView(state: Fixtures.Activities.list).previewDark()
}

#Preview("List · AX3") {
    ActivitiesSheetView(state: Fixtures.Activities.list).previewLargeType()
}

#Preview("Empty · light") {
    ActivitiesSheetView(state: Fixtures.Activities.empty)
}

#Preview("Empty · dark") {
    ActivitiesSheetView(state: Fixtures.Activities.empty).previewDark()
}

#Preview("Empty · AX3") {
    ActivitiesSheetView(state: Fixtures.Activities.empty).previewLargeType()
}
