import Foundation
import Testing
@testable import Lifeline

@Suite("API error mapping")
struct APIErrorTests {
    @Test func decodesStandardErrorBody() {
        let body = Data(#"{"error":{"code":"pending_events","message":"Answer the open events before you age.","source":"sim"}}"#.utf8)
        let error = APIError.from(status: 409, body: body)
        #expect(error == .server(status: 409, code: "pending_events", message: "Answer the open events before you age.", source: "sim"))
        #expect(error.userMessage == "Answer the open events before you age.")
    }

    @Test func unknownBodyIsUnexpected() {
        let error = APIError.from(status: 502, body: Data("<html>".utf8))
        #expect(error == .unexpected(status: 502))
        #expect(error.userMessage.contains("502"))
    }

    @Test func urlErrorIsNetwork() {
        #expect(APIError.map(URLError(.notConnectedToInternet)) == .network)
        #expect(APIError.network.userMessage.contains(Brand.productName))
    }

    @Test func unauthorizedHasFriendlyText() {
        let error = APIError.server(status: 401, code: "unauthorized", message: "Missing or invalid token.", source: "api")
        #expect(error.userMessage == "Your session ended. Try again.")
    }

    @Test func invalidInputHasPlainEnglishText() {
        let body = Data(#"{"error":{"code":"invalid_input","message":"start age must be >= 16","source":"sim"}}"#.utf8)
        let error = APIError.from(status: 422, body: body)
        #expect(error.userMessage.contains("at least 16"))
        #expect(!error.userMessage.contains(">="))
    }

    @Test func validationErrorHidesFieldNames() {
        let error = APIError.server(status: 422, code: "validation_error", message: "start_year: must be >= 1990", source: "api")
        #expect(error.userMessage == "Some details are not valid. Check them and try again.")
    }

    @Test func deviceIDMatchesContractPattern() {
        #expect(DeviceIdentity.isValid(UUID().uuidString))
        #expect(!DeviceIdentity.isValid("short"))
        #expect(!DeviceIdentity.isValid("has space in it"))
    }
}
