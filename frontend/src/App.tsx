import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import AnalyticsPage from "./pages/AnalyticsPage";
import AssessmentPage from "./pages/AssessmentPage";
import ClientsPage from "./pages/ClientsPage";
import ComparePage from "./pages/ComparePage";
import FrameworksPage from "./pages/FrameworksPage";
import ClientPage from "./pages/ClientPage";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import RemediationPage from "./pages/RemediationPage";
import SurveyPage from "./pages/SurveyPage";
import UsersPage from "./pages/UsersPage";
import { useAuth } from "./lib/auth";

export default function App() {
  const { user, loading } = useAuth();

  if (loading) return <div className="centered">Загрузка…</div>;
  if (!user) return <LoginPage />;

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/clients" replace />} />
        <Route path="/clients" element={<ClientsPage />} />
        <Route path="/clients/:clientId" element={<ClientPage />} />
        <Route path="/surveys/:surveyId" element={<SurveyPage />} />
        <Route path="/assessments/:assessmentId" element={<AssessmentPage />} />
        <Route
          path="/assessments/:assessmentId/remediation"
          element={<RemediationPage />}
        />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/assessments/compare" element={<ComparePage />} />
        <Route path="/requirements" element={<FrameworksPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="*" element={<Navigate to="/clients" replace />} />
      </Routes>
    </Layout>
  );
}
