import { Header } from "@/components/Header";
import { Dashboard } from "@/components/Dashboard";

const Index = () => {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      <Dashboard />
    </div>
  );
};

export default Index;
