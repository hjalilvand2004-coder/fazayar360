import { Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import UniversityView from "./pages/UniversityView";
import SpaceProfile from "./pages/SpaceProfile";
import SearchPage from "./pages/SearchPage";
import CalendarPage from "./pages/CalendarPage";
import Requests from "./pages/Requests";
import BookingNew from "./pages/BookingNew";
import Blocks from "./pages/Blocks";
import Equipment from "./pages/Equipment";
import Analytics from "./pages/Analytics";
import Optimizer from "./pages/Optimizer";
import Admin from "./pages/Admin";
import PublicSpace from "./pages/PublicSpace";
import { Spinner } from "./ui";

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner label="در حال بررسی نشست…" />;

  return (
    <Routes>
      {/* صفحه عمومی QR — بدون احراز هویت */}
      <Route path="/public/spaces/:slug" element={<PublicSpace />} />
      {!user ? (
        <Route path="*" element={<Login />} />
      ) : (
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/university" element={<UniversityView />} />
          <Route path="/spaces/:id" element={<SpaceProfile />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/requests" element={<Requests />} />
          <Route path="/booking-new" element={<BookingNew />} />
          <Route path="/blocks" element={<Blocks />} />
          <Route path="/equipment" element={<Equipment />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/optimizer" element={<Optimizer />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="*" element={<Dashboard />} />
        </Route>
      )}
    </Routes>
  );
}
